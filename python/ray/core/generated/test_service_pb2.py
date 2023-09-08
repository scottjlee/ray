# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: src/ray/protobuf/test_service.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n#src/ray/protobuf/test_service.proto\x12\x07ray.rpc\"\x1f\n\x0bPingRequest\x12\x10\n\x08no_reply\x18\x01 \x01(\x08\"\x0b\n\tPingReply\"\x14\n\x12PingTimeoutRequest\"\x12\n\x10PingTimeoutReply2\x86\x01\n\x0bTestService\x12\x30\n\x04Ping\x12\x14.ray.rpc.PingRequest\x1a\x12.ray.rpc.PingReply\x12\x45\n\x0bPingTimeout\x12\x1b.ray.rpc.PingTimeoutRequest\x1a\x19.ray.rpc.PingTimeoutReplyb\x06proto3')



_PINGREQUEST = DESCRIPTOR.message_types_by_name['PingRequest']
_PINGREPLY = DESCRIPTOR.message_types_by_name['PingReply']
_PINGTIMEOUTREQUEST = DESCRIPTOR.message_types_by_name['PingTimeoutRequest']
_PINGTIMEOUTREPLY = DESCRIPTOR.message_types_by_name['PingTimeoutReply']
PingRequest = _reflection.GeneratedProtocolMessageType('PingRequest', (_message.Message,), {
  'DESCRIPTOR' : _PINGREQUEST,
  '__module__' : 'src.ray.protobuf.test_service_pb2'
  # @@protoc_insertion_point(class_scope:ray.rpc.PingRequest)
  })
_sym_db.RegisterMessage(PingRequest)

PingReply = _reflection.GeneratedProtocolMessageType('PingReply', (_message.Message,), {
  'DESCRIPTOR' : _PINGREPLY,
  '__module__' : 'src.ray.protobuf.test_service_pb2'
  # @@protoc_insertion_point(class_scope:ray.rpc.PingReply)
  })
_sym_db.RegisterMessage(PingReply)

PingTimeoutRequest = _reflection.GeneratedProtocolMessageType('PingTimeoutRequest', (_message.Message,), {
  'DESCRIPTOR' : _PINGTIMEOUTREQUEST,
  '__module__' : 'src.ray.protobuf.test_service_pb2'
  # @@protoc_insertion_point(class_scope:ray.rpc.PingTimeoutRequest)
  })
_sym_db.RegisterMessage(PingTimeoutRequest)

PingTimeoutReply = _reflection.GeneratedProtocolMessageType('PingTimeoutReply', (_message.Message,), {
  'DESCRIPTOR' : _PINGTIMEOUTREPLY,
  '__module__' : 'src.ray.protobuf.test_service_pb2'
  # @@protoc_insertion_point(class_scope:ray.rpc.PingTimeoutReply)
  })
_sym_db.RegisterMessage(PingTimeoutReply)

_TESTSERVICE = DESCRIPTOR.services_by_name['TestService']
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _PINGREQUEST._serialized_start=48
  _PINGREQUEST._serialized_end=79
  _PINGREPLY._serialized_start=81
  _PINGREPLY._serialized_end=92
  _PINGTIMEOUTREQUEST._serialized_start=94
  _PINGTIMEOUTREQUEST._serialized_end=114
  _PINGTIMEOUTREPLY._serialized_start=116
  _PINGTIMEOUTREPLY._serialized_end=134
  _TESTSERVICE._serialized_start=137
  _TESTSERVICE._serialized_end=271
# @@protoc_insertion_point(module_scope)
