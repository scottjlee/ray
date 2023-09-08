# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: src/ray/protobuf/ray_syncer.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n!src/ray/protobuf/ray_syncer.proto\x12\x0eray.rpc.syncer\"{\n\x0eRaySyncMessage\x12\x0f\n\x07version\x18\x01 \x01(\x03\x12\x31\n\x0cmessage_type\x18\x02 \x01(\x0e\x32\x1b.ray.rpc.syncer.MessageType\x12\x14\n\x0csync_message\x18\x03 \x01(\x0c\x12\x0f\n\x07node_id\x18\x04 \x01(\x0c*.\n\x0bMessageType\x12\x11\n\rRESOURCE_VIEW\x10\x00\x12\x0c\n\x08\x43OMMANDS\x10\x01\x32\\\n\tRaySyncer\x12O\n\tStartSync\x12\x1e.ray.rpc.syncer.RaySyncMessage\x1a\x1e.ray.rpc.syncer.RaySyncMessage(\x01\x30\x01\x42\x03\xf8\x01\x01\x62\x06proto3')

_MESSAGETYPE = DESCRIPTOR.enum_types_by_name['MessageType']
MessageType = enum_type_wrapper.EnumTypeWrapper(_MESSAGETYPE)
RESOURCE_VIEW = 0
COMMANDS = 1


_RAYSYNCMESSAGE = DESCRIPTOR.message_types_by_name['RaySyncMessage']
RaySyncMessage = _reflection.GeneratedProtocolMessageType('RaySyncMessage', (_message.Message,), {
  'DESCRIPTOR' : _RAYSYNCMESSAGE,
  '__module__' : 'src.ray.protobuf.ray_syncer_pb2'
  # @@protoc_insertion_point(class_scope:ray.rpc.syncer.RaySyncMessage)
  })
_sym_db.RegisterMessage(RaySyncMessage)

_RAYSYNCER = DESCRIPTOR.services_by_name['RaySyncer']
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\370\001\001'
  _MESSAGETYPE._serialized_start=178
  _MESSAGETYPE._serialized_end=224
  _RAYSYNCMESSAGE._serialized_start=53
  _RAYSYNCMESSAGE._serialized_end=176
  _RAYSYNCER._serialized_start=226
  _RAYSYNCER._serialized_end=318
# @@protoc_insertion_point(module_scope)
