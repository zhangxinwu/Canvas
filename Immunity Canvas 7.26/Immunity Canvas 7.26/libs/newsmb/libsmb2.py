#### SMB2
####
#### NOTE:
#### In the case of structure fields that are embedded inside other fields
#### (such as FileName in Buffer, or data/name in read/write methods etc)
#### i think it's better if we define them as virtual fields (specifier '0s')
#### in the actual structure definition so that they are easily visible instead
#### of using method attributes (variables) that are created in the
#### constructor. In that way we don't lose any flexibility and we can treat
#### them as regular structure fields (Chris)
####

import sys
import random
from struct import pack, unpack

if '.' not in sys.path:
    sys.path.append('.')

from libs.newsmb.libgssapi import GSSAPI, GSS_NTLMSSP, GSS_KRB5
from libs.newsmb.libntlm import NTLM
from libs.newsmb.Struct import Struct
from libs.newsmb.smb2const import *

AUTHOR="nicolasp"
NOTES="""
Version 1 - 03/24/09
"""

def align8(num):
    """
    Return num aligned to an 8-byte boundary.
    """
    if num % 8 == 0:
        return num
    else:
        return (num&0xfff8)+8

def pad8(name):
    """
    Return string name padded to an 8-byte boundary.
    """
    if len(name) % 8:
        name = name + ('\0' * (8-len(name)%8))

    return name


class SMB2Header(Struct):
    st = [
        ['ProtocolId'             , '4s', '\xFESMB'],
        ['StructureSize'          , '<H', SMB2_HEADER_SIZE],
        ['CreditCharge'           , '<H', 0],
        ['Status'                 , '<L', 0],
        ['Command'                , '<H', 0],
        ['CreditRequestResponse'  , '<H', 126],
        ['Flags'                  , '<L', 0],
        ['NextCommand'            , '<L', 0],
        ['MessageId'              , '<Q', 0],
        ['ProcessId'              , '<L', 0],
        ['TreeId'                 , '<L', 0],
        ['SessionId'              , '<Q', 0],
        ['Signature'              , '16s', '\0'*16],
    ]


class SMB2ErrorResponse(Struct):
    st = [
        ['StructureSize' , '<H', 9],
        ['Reserved'      , '<H', 0],
        ['ByteCount'     , '<L', 0],
        ['ErrorData'     , '0s', ''],
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self.calcsize()
            self['ErrorData'] = data[pos:pos+self['ByteCount']]

    def pack(self):
        self['ByteCount'] = len(self['ErrorData'])
        return Struct.pack(self) + self['ErrorData']


class SMB2SymlinkErrorResponse(Struct):
    st = [
        ['SymLinkLength'         , '<L', 0],
        ['SymLinkErrorTag'       , '<L', 0x4c4d5953],
        ['ReparseTag'            , '<L', 0xA000000C],
        ['ReparseDataLength'     , '<H', 0],
        ['UnparsedPathLength'    , '<H', 0],
        ['SubstituteNameOffset'  , '<H', 0],
        ['SubstituteNameLength'  , '<H', 0],
        ['PrintNameOffset'       , '<H', 0],
        ['PrintNameLength'       , '<H', 0],
        ['Flags'                 , '<L', 0],
        ['PathBuffer'            , '0s', ''],
        ['SubstituteName'        , '0s', ''], # Virtual field, part of PathBuffer
        ['PrintName'             , '0s', ''], # Virtual field, part of PathBuffer
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self.calcsize()
            re_length = self['ReparseDataLength']-12
            sub_offset = self['SubstituteNameOffset']
            sub_length = self['SubstituteNameLength']
            print_offset = self['PrintNameOffset']
            print_length = self['PrintNameLength']
            self['PathBuffer'] = data[pos:pos+re_length]

            self['SubstituteName'] = self['PathBuffer'][sub_offset:sub_offset+sub_length]

            if sub_length > 0:
                self['SubstituteName'] = self['SubstituteName'].decode('UTF-16LE')

            self['PrintName'] = self['PathBuffer'][print_offset:print_offset+print_length]

            if print_length > 0:
                self['PrintName'] = self['PrintName'].decode('UTF-16LE')

    def pack(self):
        sub_name = self['SubstituteName'].encode('UTF-16LE')
        print_name = self['PrintName'].encode('UTF-16LE')

        self['SubstituteNameOffset'] = 0
        self['SubstituteNameLength'] = len(sub_name)

        self['PrintNameOffset'] = self['SubstituteNameLength']
        self['PrintNameLength'] = len(print_name)

        self['PathBuffer'] = sub_name + print_name

        self['SymLinkLength'] = len(self['PathBuffer']) + 24
        self['ReparseDataLength'] = len(self['PathBuffer']) + 12
        return Struct.pack(self) + self['PathBuffer']


class SMB2NegotiateRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 36],
        ['DialectCount'   , '<H', 1],
        ['SecurityMode'   , '<H', SMB2_NEGOTIATE_SIGNING_ENABLED],
        ['Reserved'       , '<H', 0],
        ['Capabilities'   , '<L', 0],
        ['ClientGuid'     , '16s', '\0'*16],
        ['ClientStartTime', '<Q', 0],
        ['Dialects'       , '0s', ''],
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)
        if data is not None:
            count = self['DialectCount']
            pos = self.calcsize()
            self['Dialects'] = data[pos:pos+(count*2)]

    def pack(self):
        if self['Dialects'] == '':
            self['Dialects'] = pack('<H', DIALECT_SMB_202)
            self['DialectCount'] = 1
        else:
            self['DialectCount'] = len(self['Dialects'])/2
        return Struct.pack(self) + self['Dialects']

class SMB2NegotiateResponse(Struct):
    st = [
        ['StructureSize'         , '<H', 65],
        ['SecurityMode'          , '<H', SMB2_NEGOTIATE_SIGNING_ENABLED],
        ['DialectRevision'       , '<H', 0x02FF], # Wildcard dialect
        ['Reserved'              , '<H', 0],
        ['ServerGuid'            , '16s', '\0'*16],
        ['Capabilities'          , '<L', 0],
        ['MaxTransactSize'       , '<L', 0],
        ['MaxReadSize'           , '<L', 0],
        ['MaxWriteSize'          , '<L', 0],
        ['SystemTime'            , '<Q', 0],
        ['ServerStartTime'       , '<Q', 0],
        ['SecurityBufferOffset'  , '<H', 0],
        ['SecurityBufferLength'  , '<H', 0],
        ['Reserved2'             , '<L', 0],
        ['Buffer'                , '0s', ''],
    ]

    def __init__(self, data = None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['SecurityBufferOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['SecurityBufferLength']]

    def pack(self):
        self['SecurityBufferOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE
        self['SecurityBufferLength'] = len(self['Buffer'])

        return Struct.pack(self) + self['Buffer']


class SMB2SessionSetupRequest(Struct):
    st = [
        ['StructureSize'        , '<H', 25],
        ['VcNumber'             , '<B', 0],
        ['SecurityMode'         , '<B', SMB2_NEGOTIATE_SIGNING_ENABLED],
        ['Capabilities'         , '<L', 0],
        ['Channel'              , '<L', 0],
        ['SecurityBufferOffset' , '<H', 0],
        ['SecurityBufferLength' , '<H', 0],
        ['PreviousSessionId'    , '<Q', 0],
        ['Buffer'               , '0s', '']
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['SecurityBufferOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['SecurityBufferLength']]

    def pack(self):
        self['SecurityBufferOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['SecurityBufferLength'] = len(self['Buffer'])
        return Struct.pack(self) + self['Buffer']


class SMB2SessionSetupResponse(Struct):
    st = [
        ['StructureSize'         , '<H', 9],
        ['SessionFlags'          , '<H', 0],
        ['SecurityBufferOffset'  , '<H', 0],
        ['SecurityBufferLength'  , '<H', 0],
        ['Buffer'                , '0s', '']
    ]

    def __init__(self, data = None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['SecurityBufferOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['SecurityBufferLength']]

    def pack(self):
        self['SecurityBufferOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['SecurityBufferLength'] = len(self['Buffer'])
        data = Struct.pack(self)

        return data + self['Buffer']


class SMB2LogoffRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]


class SMB2LogoffResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]

class SMB2TreeConnectRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 9],
        ['Reserved'       , '<H', 0],
        ['PathOffset'     , '<H', 0],
        ['PathLength'     , '<H', 0],
        ['Buffer'         , '0s', '']
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['PathOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['PathLength']].decode('UTF-16LE')

    def pack(self):
        self['PathOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        path = self['Buffer'].encode('UTF-16LE')

        self['PathLength'] = len(path)
        return Struct.pack(self) + path


class SMB2TreeConnectResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 16],
        ['ShareType'      , '<B', 0],
        ['Reserved'       , '<B', 0],
        ['ShareFlags'     , '<L', 0],
        ['Capabilities'   , '<L', 0],
        ['MaximalAccess'  , '<L', 0],
    ]


class SMB2TreeDisconnectRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]


class SMB2TreeDisconnectResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]

class SMB2CreateContext(Struct):
    st = [
        ['Next'           , '<L', 0],
        ['NameOffset'     , '<H', 0],
        ['NameLength'     , '<H', 0],
        ['Reserved'       , '<H', 0],
        ['DataOffset'     , '<H', 0],
        ['DataLength'     , '<L', 0],
        ['Buffer'         , '0s', ''],
        ['Name'           , '0s', ''], # Virtual field, part of Buffer
        ['Data'           , '0s', ''], # Virtual field, part of Buffer
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)
        if data is not None:
            pos = self['NameOffset']
            self['Name'] = data[pos:pos+self['NameLength']]
            pos = self['DataOffset']
            self['Data'] = data[pos:pos+self['DataLength']]
            self['Buffer'] = self['Name'] + self['Data']

    def pack(self):
        self['NameOffset'] = 16
        self['NameLength'] = len(self['Name'])
        self['DataOffset'] = self['NameOffset'] + 8
        self['DataLength'] = len(self['Data'])
        self['Buffer'] = pad8(self['Name']) + self['Data']

        return Struct.pack(self) + self['Buffer']


class SMB2CreateRequest(Struct):
    st = [
        ['StructureSize'        , '<H', 57],
        ['SecurityFlags'        , '<B', 0],
        ['RequestedOplockLevel' , '<B', SMB2_OPLOCK_LEVEL_NONE],
        ['ImpersonationLevel'   , '<L', IMPERSONATION_IDENTIFICATION],
        ['SmbCreateFlags'       , '<Q', 0],
        ['Reserved'             , '<Q', 0],
        ['DesiredAccess'        , '<L', 0],
        ['FileAttributes'       , '<L', 0],
        ['ShareAccess'          , '<L', 0],
        ['CreateDisposition'    , '<L', 0],
        ['CreateOptions'        , '<L', 0],
        ['NameOffset'           , '<H', 0],
        ['NameLength'           , '<H', 0],
        ['CreateContextsOffset' , '<L', 0],
        ['CreateContextsLength' , '<L', 0],
        ['Buffer'               , '0s', ''],
        ['Name'                 , '0s', ''], # Virtual field, part of Buffer
        ['CreateContexts'       , '0s', ''], # Virtual field, part of Buffer
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['NameOffset'] - SMB2_HEADER_SIZE
            self['Name'] = data[pos:pos+self['NameLength']]

            pos = self['CreateContextsOffset'] - SMB2_HEADER_SIZE
            self['CreateContexts'] = data[pos:pos+self['CreateContextsLength']]

            self['Buffer'] = self['Name'] + self['CreateContexts']

            if self['NameLength'] > 0:
                self['Name'] = self['Name'].decode('UTF-16LE')
            else:
                self['Name'] = ''


    def pack(self):
        # TODO: Check alignment
        name = self['Name'].encode('UTF-16LE')
        self['NameOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['NameLength'] = len(name)

        offset = self['StructureSize'] + self['NameLength'] + SMB2_HEADER_SIZE - 1

        if offset % 8: # Make sure contexts list is 8-byte aligned
            offset_aligned = align8(offset)
            pad = offset_aligned - offset
            self['CreateContextsOffset'] = offset_aligned
            pad = '\0'*pad
        else:
            self['CreateContextsOffset'] = offset
            pad = ''

        self['CreateContextsLength'] = len(self['CreateContexts'])
        self['Buffer'] = self['Name'] + pad + self['CreateContexts']

        return Struct.pack(self) + self['Buffer']


class SMB2CreateResponse(Struct):
    st = [
        ['StructureSize'        , '<H', 89],
        ['OplockLevel'          , '<B', 0],
        ['Reserved'             , '<B', 0],
        ['CreateAction'         , '<L', 0],
        ['CreationTime'         , '<Q', 0],
        ['LastAccessTime'       , '<Q', 0],
        ['LastWriteTime'        , '<Q', 0],
        ['ChangeTime'           , '<Q', 0],
        ['AllocationSize'       , '<Q', 0],
        ['EndofFile'            , '<Q', 0],
        ['FileAttributes'       , '<L', 0],
        ['Reserved2'            , '<L', 0],
        ['FileId'               , '16s', '\0'*16],
        ['CreateContextsOffset' , '<L', 0],
        ['CreateContextsLength' , '<L', 0],
        ['Buffer'               , '0s', ''],
        ['CreateContexts'       , '0s', ''], # Virtual field, part of Buffer
    ]

    def __init__(self, data = None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['CreateContextsOffset'] - SMB2_HEADER_SIZE
            self['CreateContexts'] = data[pos:pos+self['CreateContextsLength']]
            self['Buffer'] = self['CreateContexts']

    def pack(self):
        self['CreateContextsOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['CreateContextsLength'] = len(self['CreateContexts'])
        self['Buffer'] = self['CreateContexts']

        return Struct.pack(self) + self['Buffer']



class SMB2CloseRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 24],
        ['Flags'          , '<H', 0],
        ['Reserved'       , '<L', 0],
        ['FileId'         , '16s', '\0'*16],
    ]


class SMB2CloseResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 60],
        ['Flags'          , '<H', 0],
        ['Reserved'       , '<L', 0],
        ['CreationTime'   , '<Q', 0],
        ['LastAccessTime' , '<Q', 0],
        ['LastWriteTime'  , '<Q', 0],
        ['ChangeTime'     , '<Q', 0],
        ['AllocationSize' , '<Q', 0],
        ['EndofFile'      , '<Q', 0],
        ['FileAttributes' , '<L', 0],
    ]


class SMB2FlushRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 24],
        ['Reserved1'      , '<H', 0],
        ['Reserved2'      , '<L', 0],
        ['FileId'         , '16s', '\0'*16],
    ]

class SMB2FlushResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]

class SMB2ReadRequest(Struct):
    st = [
        ['StructureSize'         , '<H', 49],
        ['Padding'               , '<B', 0],
        ['Reserved'              , '<B', 0],
        ['Length'                , '<L', 0],
        ['Offset'                , '<Q', 0],
        ['FileId'                , '16s', '\0'*16],
        ['MinimumCount'          , '<L', 0],
        ['Channel'               , '<L', 0],
        ['RemainingBytes'        , '<L', 0],
        ['ReadChannelInfoOffset' , '<H', 0],
        ['ReadChannelInfoLength' , '<H', 0],
        ['Buffer'                , '0s', ''],
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['ReadChannelInfoOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['ReadChannelInfoLength']]

    def pack(self):
        self['ReadChannelInfoOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['Buffer'] = '\x00'

        return Struct.pack(self) + self['Buffer']


class SMB2ReadResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 17],
        ['DataOffset'     , '<B', 0],
        ['Reserved'       , '<B', 0],
        ['DataLength'     , '<L', 0],
        ['DataRemaining'  , '<L', 0],
        ['Reserved2'      , '<L', 0],
        ['Buffer'         , '0s', ''],
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['DataOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['DataLength']]

    def pack(self):
        self['DataOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['DataLength'] = len(self['Buffer'])

        return Struct.pack(self) + self['Buffer']


class SMB2WriteRequest(Struct):
    st = [
        ['StructureSize'            , '<H', 49],
        ['DataOffset'               , '<H', 0],
        ['Length'                   , '<L', 0],
        ['Offset'                   , '<Q', 0],
        ['FileId'                   , '16s', '\0'*16],
        ['Channel'                  , '<L', 0],
        ['RemainingBytes'           , '<L', 0],
        ['WriteChannelInfoOffset'   , '<H', 0],
        ['WriteChannelInfoLength'   , '<H', 0],
        ['Flags'                    , '<L', 0],
        ['Buffer'                   , '0s', ''],
        ['Data'                     , '0s', ''], # Virtual field, part of Buffer
        ['ChannelInfo'              , '0s', ''], # Virtual field, part of Buffer
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['DataOffset'] - SMB2_HEADER_SIZE
            self['Data'] = data[pos:pos+self['Length']]
            pos = self['WriteChannelInfoOffset'] - SMB2_HEADER_SIZE
            self['ChannelInfo'] = data[pos:pos+self['WriteChannelInfoLength']]

            self['Buffer'] = self['Data'] + self['ChannelInfo']

    def pack(self):
        self['DataOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['Length'] = len(self['Data'])
        self['WriteChannelInfoOffset'] = self['StructureSize'] + self['Length'] + SMB2_HEADER_SIZE - 1
        self['WriteChannelInfoLength'] = len(self['ChannelInfo'])
        self['Buffer'] = self['Data'] + self['ChannelInfo']

        return Struct.pack(self) + self['Buffer']


class SMB2WriteResponse(Struct):
    st = [
        ['StructureSize'          , '<H', 17],
        ['Reserved'               , '<H', 0],
        ['Count'                  , '<L', 0],
        ['Remaining'              , '<L', 0],
        ['WriteChannelInfoOffset' , '<H', 0],
        ['WriteChannelInfoLength' , '<H', 0],
    ]


class SMB2OplockBreakRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 24],
        ['OplockLevel'    , '<B', 0],
        ['Reserved'       , '<B', 0],
        ['Reserved2'      , '<L', 0],
        ['FileId'         , '16s', '\0'*16],
    ]

class SMB2OplockBreakAcknowledgment(SMB2OplockBreakRequest):
    pass


class SMB2OplockBreakResponse(SMB2OplockBreakRequest):
    pass


class SMB2LeaseBreakRequest(Struct):
    st = [
        ['StructureSize'      , '<H', 44],
        ['Reserved'           , '<H', 0],
        ['Flags'              , '<L', 0],
        ['LeaseKey'           , '16s', '\0'*16],
        ['CurrentLeaseState'  , '<L', 0],
        ['NewLeaseState'      , '<L', 0],
        ['BreakReason'        , '<L', 0],
        ['AccessMaskHint'     , '<L', 0],
        ['ShareMaskHint'      , '<L', 0],
    ]


class SMB2LeaseBreakAcknowledgment(Struct):
    st = [
        ['StructureSize'      , '<H', 36],
        ['Reserved'           , '<H', 0],
        ['Flags'              , '<L', 0],
        ['LeaseKey'           , '16s', '\0'*16],
        ['LeaseState'         , '<L', 0],
        ['LeaseDuration'      , '<Q', 0],
    ]



class SMB2LeaseBreakResponse(SMB2LeaseBreakAcknowledgment):
    pass



class SMB2LockElement(Struct):
    st = [
        ['Offset'         , '<Q', 0],
        ['Length'         , '<Q', 0],
        ['Flags'          , '<L', 0],
        ['Reserved'       , '<L', 0],
    ]


class SMB2LockRequest(Struct):
    st = [
        # Structure size should include 1 lock element, 24 + 24
        ['StructureSize'  , '<H', 48],
        ['LockCount'      , '<H', 0],
        ['Reserved'       , '<L', 0],
        ['FileId'         , '16s', '\0'*16],
        ['Locks'          , '0s', ''],
    ]

    def __init__(self, data = None):
        Struct.__init__(self, data)

        if data is not None:
            # Size of SMB2_LOCK_ELEMENT structure is 24 bytes
            self['Locks'] = data[24:24+self['LockCount']*24]

    def pack(self):
        return Struct.pack(self) + self['Locks']


class SMB2LockResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]


class SMB2EchoRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]


class SMB2EchoResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]


class SMB2CancelRequest(Struct):
    st = [
        ['StructureSize'  , '<H', 4],
        ['Reserved'       , '<H', 0],
    ]


class SrvCopyChunk(Struct):
    st = [
        ['SourceOffset'  , '<Q', 0],
        ['TargetOffset'  , '<Q', 0],
        ['Length'        , '<L', 0],
        ['Reserved'      , '<L', 0],
    ]


class SrvCopyChunkCopy(Struct):
    st = [
        ['SourceKey'      , '24s', '\0'*4],
        ['ChunkCount'     , '<L', 0],
        ['Reserved'       , '<L', 0],
        ['Chunks'         , '0s', ''],
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self.calcsize()
            self['Chunks'] = data[pos:pos+self['ChunkCount']*24] # Size of SrvCopyChunk

    def pack(self):
        self['ChunkCount'] = len(self['Chunks']) / 24
        return Struct.pack(self) + self['Chunks']

class SrvReadHash(Struct):
    st = [
        ['HashType'           , '<L', 1], # SRV_HASH_TYPE_PEER_DIST
        ['HashVersion'        , '<L', 1], # SRV_HASH_VER_1
        ['HashRetrievalType'  , '<L', 1], # SRV_HASH_RETRIEVE_HASH_BASED
        ['Length'             , '<L', 0],
        ['Offset'             , '<L', 0],
    ]


class HashHeader(Struct):
    st = [
        ['HashType'              , '<L', 1], # SRV_HASH_TYPE_PEER_DIST
        ['HashVersion'           , '<L', 1], # SRv_HASH_VER_1
        ['SourceFileChangeTime'  , '<Q', 0],
        ['SourceFileSize'        , '<Q', 0],
        ['HashBlobLength'        , '<L', 0],
        ['HashBlobOffset'        , '<L', 0],
        ['Dirty'                 , '<H', 0],
        ['SourceFileNameLength'  , '<H', 0],
        ['SourceFileName'        , '0s', ''],
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self.calcsize()
            length = self['SourceFileNameLength']
            self['SourceFileName'] = ''

            if length > 0:
                self['SourceFileName'] = data[pos:pos+length].decode('UTF-16LE')

    def pack(self):
        filename = self['SourceFileName'].encode('UTF-16LE')
        self['SourceFileNameLength'] = len(filename)

        return Struct.pack(self) + filename


class NetworkResiliencyRequest(Struct):
    st = [
        ['Timeout'          , '<L', 0],
        ['Reserved'         , '<L', 0],
    ]


class SMB2IoctlRequest(Struct):
    st = [
        ['StructureSize'    , '<H', 57],
        ['Reserved'         , '<H', 0],
        ['CtlCode'          , '<L', 0],
        ['FileId'           , '16s', '\0'*16],
        ['InputOffset'      , '<L', 0],
        ['InputCount'       , '<L', 0],
        ['MaxInputResponse' , '<L', 10],
        ['OutputOffset'     , '<L', 0],
        ['OutputCount'      , '<L', 0],
        ['MaxOutputResponse', '<L', 10],
        ['Flags'            , '<L', 0],
        ['Reserved2'        , '<L', 0],
        ['Buffer'           , '0s', ''],
        ['Input'            , '0s', ''], # Virtual field, part of Buffer
        ['Output'           , '0s', ''], # Virtual field, part of Buffer
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['InputOffset'] - SMB2_HEADER_SIZE
            self['Input'] = data[pos:pos+self['InputCount']]
            pos = self['OutputOffset'] - SMB2_HEADER_SIZE
            self['Output'] = data[pos:pos+self['OutputCount']]

            self['Buffer'] = self['Input'] + self['Output']

    def pack(self):
        self['InputOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['InputCount'] = len(self['Input'])
        self['OutputOffset'] = self['InputOffset'] + self['InputCount']
        self['OutputCount'] = len(self['Output'])
        self['Buffer'] = self['Input'] + self['Output']

        return Struct.pack(self) + self['Buffer']


class SMB2IoctlResponse(Struct):
    st = [
        ['StructureSize'    , '<H', 49],
        ['Reserved'         , '<H', 0],
        ['CtlCode'          , '<L', 0],
        ['FileId'           , '16s', '\0'*16],
        ['InputOffset'      , '<L', 0],
        ['InputCount'       , '<L', 0],
        ['OutputOffset'     , '<L', 0],
        ['OutputCount'      , '<L', 0],
        ['Flags'            , '<L', 0],
        ['Reserved2'        , '<L', 0],
        ['Buffer'           , '0s', ''],
        ['Input'            , '0s', ''], # Virtual field, part of Buffer
        ['Output'           , '0s', ''], # Virtual field, part of Buffer
    ]

    def __init__(self, data = None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['InputOffset'] - SMB2_HEADER_SIZE
            self['Input'] = data[pos:pos+self['InputCount']]
            pos = self['OutputOffset'] - SMB2_HEADER_SIZE
            self['Output'] = data[pos:pos+self['OutputCount']]
            self['Buffer'] = self['Input'] + self['Output']


    def pack(self):
        self['InputOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['InputCount'] = len(self['Input'])
        self['OutputOffset'] = self['InputOffset'] + self['InputCount']
        self['OutputCount'] = len(self['Output'])
        self['Buffer'] = self['Input'] + self['Output']

        return Struct.pack(self) + self['Buffer']


class SMB2QueryDirectoryRequest(Struct):
    st = [
        ['StructureSize'        , '<H', 33],
        ['FileInformationClass' , '<B', 0],
        ['Flags'                , '<B', 0],
        ['FileIndex'            , '<L', 0],
        ['FileId'               , '16s', '\0'*16],
        ['FileNameOffset'       , '<H', 0],
        ['FileNameLength'       , '<H', 0],
        ['OutputBufferLength'   , '<L', 0],
        ['Buffer'               , '0s', ''],
        ['FileName'             , '0s', ''], # Virtual field, part of Buffer
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['FileNameOffset'] - SMB2_HEADER_SIZE
            self['FileName'] = data[pos:pos+self['FileNameLength']]
            self['Buffer'] = self['FileName']

            if self['FileNameLength'] > 0:
                self['FileName'] = self['FileName'].decode('UTF-16LE')

    def pack(self):
        self['FileNameOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        filename = self['FileName'].encode('UTF-16LE')

        self['FileNameLength'] = len(filename)
        self['Buffer'] = filename

        return Struct.pack(self) + filename


class SMB2QueryDirectoryResponse(Struct):
    st = [
        ['StructureSize'       , '<H', 9],
        ['OutputBufferOffset'  , '<H', 0],
        ['OutputBufferLength'  , '<L', 0],
        ['Buffer'              , '0s', ''],
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['OutputBufferOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['OutputBufferLength']]


    def pack(self):
        self['OutputBufferOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['OutputBufferLength'] = len(self['Buffer'])

        return Struct.pack(self) + self['Buffer']



class SMB2ChangeNotifyRequest(Struct):
    st = [
        ['StructureSize'      , '<H', 32],
        ['Flags'              , '<H', 0],
        ['OutputBufferLength' , '<L', 0],
        ['FileId'             , '16s', '\0'*16],
        ['CompletionFilter'   , '<L', 0],
        ['Reserved'           , '<L', 0],
    ]


class SMB2ChangeNotifyResponse(Struct):
    st = [
        ['StructureSize'       , '<H', 9],
        ['OutputBufferOffset'  , '<H', 0],
        ['OutputBufferLength'  , '<L', 0],
        ['Buffer'              , '0s', ''],
    ]

    def __init__(self, data = None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['OutputBufferOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['OutputBufferLength']]

    def pack(self):
        self['OutputBufferOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['OutputBufferLength'] = len(self['Buffer'])

        return Struct.pack(self) + self['Buffer']



class SMB2QueryInfoRequest(Struct):
    st = [
        ['StructureSize'         , '<H', 41],
        ['InfoType'              , '<B', 0],
        ['FileInfoClass'         , '<B', 0],
        ['OutputBufferLength'    , '<L', 0],
        ['InputBufferOffset'     , '<H', 0],
        ['Reserved'              , '<H', 0],
        ['InputBufferLength'     , '<L', 0],
        ['AdditionalInformation' , '<L', 0],
        ['Flags'                 , '<L', 0],
        ['FileId'                , '16s', '\0'*16],
        ['Buffer'                , '0s', '']
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['InputBufferOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['InputBufferLength']]

    def pack(self):
        self['InputBufferOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['InputBufferLength'] = len(self['Buffer'])

        return Struct.pack(self) + self['Buffer']


class SMB2QueryInfoResponse(Struct):
    st = [
        ['StructureSize'       , '<H', 9],
        ['OutputBufferOffset'  , '<H', 0],
        ['OutputBufferLength'  , '<L', 0],
        ['Buffer'              , '0s', ''],
    ]

    def __init__(self, data = None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['OutputBufferOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['OutputBufferLength']]

    def pack(self):
        self['OutputBufferOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['OutputBufferLength'] = len(self['Buffer'])

        return Struct.pack(self) + self['Buffer']



class SMB2SetInfoRequest(Struct):
    st = [
        ['StructureSize'            , '<H', 33],
        ['InfoType'                 , '<B', 0],
        ['FileInfoClass'            , '<B', 0],
        ['BufferLength'             , '<L', 0],
        ['BufferOffset'             , '<H', 0],
        ['Reserved'                 , '<H', 0],
        ['AdditionalInformation'    , '<L', 0],
        ['FileId'                   , '16s', '\0'*16],
        ['Buffer'                   , '0s', '']
    ]

    def __init__(self, data=None):
        Struct.__init__(self, data)

        if data is not None:
            pos = self['BufferOffset'] - SMB2_HEADER_SIZE
            self['Buffer'] = data[pos:pos+self['BufferLength']]

    def pack(self):
        self['BufferOffset'] = self['StructureSize'] + SMB2_HEADER_SIZE - 1
        self['BufferLength'] = len(self['Buffer'])

        return Struct.pack(self) + self['Buffer']


class SMB2SetInfoResponse(Struct):
    st = [
        ['StructureSize'  , '<H', 2],
    ]


class SMB2Packet():
    def __init__(self, data=None, command=0, mid=0, pid=0, tid=0, sid=0, server=0):
        self.header = SMB2Header(data)

        if data is not None:
            server = (~server) & 0x01
            command = self.header['Command']
            data = data[SMB2_HEADER_SIZE:]
        else:
            self.header['Command'] = command
            self.header['MessageId'] = mid
            self.header['TreeId'] = tid
            self.header['ProcessId'] = pid
            self.header['SessionId'] = sid

        smb_response = {
            SMB2_ERROR:           SMB2ErrorResponse,
            SMB2_NEGOTIATE:       SMB2NegotiateResponse,
            SMB2_SESSION_SETUP:   SMB2SessionSetupResponse,
            SMB2_LOGOFF:          SMB2LogoffResponse,
            SMB2_TREE_CONNECT:    SMB2TreeConnectResponse,
            SMB2_TREE_DISCONNECT: SMB2TreeDisconnectResponse,
            SMB2_CREATE:          SMB2CreateResponse,
            SMB2_CLOSE:           SMB2CloseResponse,
            SMB2_FLUSH:           SMB2FlushResponse,
            SMB2_READ:            SMB2ReadResponse,
            SMB2_WRITE:           SMB2WriteResponse,
            SMB2_LOCK:            SMB2LockResponse,
            SMB2_IOCTL:           SMB2IoctlResponse,
            SMB2_ECHO:            SMB2EchoResponse,
            SMB2_QUERY_DIRECTORY: SMB2QueryDirectoryResponse,
            SMB2_CHANGE_NOTIFY:   SMB2ChangeNotifyResponse,
            SMB2_QUERY_INFO:      SMB2QueryInfoResponse,
            SMB2_SET_INFO:        SMB2SetInfoResponse,
            SMB2_OPLOCK_BREAK:    SMB2OplockBreakResponse
        }

        smb_request = {
            SMB2_NEGOTIATE:       SMB2NegotiateRequest,
            SMB2_SESSION_SETUP:   SMB2SessionSetupRequest,
            SMB2_LOGOFF:          SMB2LogoffRequest,
            SMB2_TREE_CONNECT:    SMB2TreeConnectRequest,
            SMB2_TREE_DISCONNECT: SMB2TreeDisconnectRequest,
            SMB2_CREATE:          SMB2CreateRequest,
            SMB2_CLOSE:           SMB2CloseRequest,
            SMB2_FLUSH:           SMB2FlushRequest,
            SMB2_READ:            SMB2ReadRequest,
            SMB2_WRITE:           SMB2WriteRequest,
            SMB2_LOCK:            SMB2LockRequest,
            SMB2_IOCTL:           SMB2IoctlRequest,
            SMB2_CANCEL:          SMB2CancelRequest,
            SMB2_ECHO:            SMB2EchoRequest,
            SMB2_QUERY_DIRECTORY: SMB2QueryDirectoryRequest,
            SMB2_CHANGE_NOTIFY:   SMB2ChangeNotifyRequest,
            SMB2_QUERY_INFO:      SMB2QueryInfoRequest,
            SMB2_SET_INFO:        SMB2SetInfoRequest,
            SMB2_OPLOCK_BREAK:    SMB2OplockBreakRequest
        }

        if self.header['Status'] != 0:
            command = SMB2_ERROR

        if server == 1:
            self.body = smb_response[command](data)
        else:
            self.body = smb_request[command](data)

    def pack(self):
        return self.header.pack() + self.body.pack()


class SMB2Exception(Exception):
    """
    Base class for all SMB2 Exceptions
    """
    pass


class SMB2:
    def __init__(self, socket):
        self.socket = socket
        self.mid = 0         # MessageId
        self.pid = 0         # ProcessId
        self.tid = 0         # TreeId
        self.sid = 0         # SessionId

    def recv(self):
        data = self.socket.recv(4)

        if data == '':
            raise SMB2Exception('Remote end closed connection.')

        type, hlen, llen = unpack('>BBH', data)
        total_length = (hlen << 16) + llen
        data = ''
        length = 0

        while length < total_length:
            chunk = self.socket.recv(total_length - length)
            if chunk == '':
                raise SMB2Exception('Remote end closed connection.')

            data += chunk
            length += len(chunk)

        self.packet = SMB2Packet(data)

    def send(self):
        data = self.packet.pack()
        length = len(data)
        self.socket.sendall(pack('>BBH', 0, (length >> 16) & 0xFF, length & 0xFFFF) + data)
        self.mid = self.mid + 1

    def send_recv(self):
        self.send()
        self.recv()



class SMB2Client(SMB2):
    def __init__(self, socket, username=u'', password=u'', workstation=u'', domain=u''):
        SMB2.__init__(self, socket)
        self.username    = username
        self.password    = password
        self.workstation = workstation
        self.domain      = domain

    def negotiate(self):
        self.packet                    = SMB2Packet(None, SMB2_NEGOTIATE, self.mid, self.pid, self.tid, self.sid)
        self.packet.body['ClientGuid'] ='Y'*16
        self.pid                       = random.randint(0,0xFFFFFFFF)
        self.send_recv()

    def session_setup(self):
        self.packet = SMB2Packet(None, SMB2_SESSION_SETUP, self.mid, self.pid, self.tid, self.sid)

        auth=NTLM(self.username, self.password, self.workstation, self.domain)

        #auth.set_type(NTLMSSP_NEGOTIATE)
        #auth.set_flag(0x80005)

        gss = GSSAPI(None, True)
        gss.spnego_init(auth.negotiate())

        self.packet.body["Buffer"] = gss.pack()
        self.send_recv()

        self.sid = self.packet.header['SessionId']

        # STATUS_MORE_PROCESSING_REQUIRED
        if self.packet.header['Status'] == 0xC0000016:
            auth = NTLM()
            #XX Use gssapi XX
            i=self.packet.body['Buffer'].find('NTLMSSP')
            auth.challenge(self.packet.body['Buffer'][i:])
            # auth.get(self.packet.body['Buffer'][i:])
            # auth.username = self.username
            # auth.password = self.password
            # auth.domain = self.domain
            # auth.set_unicode(1)
            # auth.set_ntlm_version(2)
            # auth.set_type(NTLMSSP_AUTH)
            # auth.set_flag(0x80005)

            gss = GSSAPI()
            gss.spnego_cont(auth.authenticate())

            #gss.spnego_cont(auth.raw())

            self.packet = SMB2Packet(None, SMB2_SESSION_SETUP, self.mid, self.pid, self.tid, self.sid)
            self.packet.body['SecurityMode'] = 0
            self.packet.body['Buffer'] = gss.pack()
            self.send_recv()

    def tree_connect(self, share, vhost = ''):
        self.packet = SMB2Packet(None, SMB2_TREE_CONNECT, self.mid, self.pid, self.tid, self.sid)
        if vhost=='':
            vhost=self.socket.getpeername()[0]
        self.packet.body['Buffer'] = ("\\\\" + vhost + "\\" + share).encode('utf16')[2:]
        self.send_recv()
        self.tid = self.packet.header['TreeId']

    def tree_disconnect(self):
        self.packet = SMB2Packet(None, SMB2_TREE_DISCONNECT, self.mid, self.pid, self.tid, self.sid)
        self.send_recv()

    def logoff(self):
        self.packet = SMB2Packet(None, SMB2_LOGOFF, self.mid, self.pid, self.tid, self.sid)
        self.send_recv()

    def create(self, name, desiredaccess, fileattributes, shareaccess, createdisposition, createoptions):
        self.packet = SMB2Packet(None, SMB2_CREATE, self.mid, self.pid, self.tid, self.sid)
        self.packet.body['Name'] = name.encode('utf16')[2:]
        self.packet.body['DesiredAccess'] = desiredaccess
        self.packet.body['FileAttributes'] = fileattributes
        self.packet.body['ShareAccess'] = shareaccess
        self.packet.body['CreateDisposition'] = createdisposition
        self.packet.body['CreateOptions'] = createoptions
        self.send_recv()

        status = self.packet.header['Status']
        if status == 0:
            return self.packet.body['FileId']
        else:
            return None

    def close(self, fid, flags=0):
        self.packet = SMB2Packet(None, SMB2_CLOSE, self.mid, self.pid, self.tid, self.sid)
        self.packet.body['FileId'] = fid
        self.packet.body['Flags'] = flags
        self.send_recv()