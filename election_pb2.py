# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: election.proto
# Protobuf Python Version: 5.26.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0e\x65lection.proto\x12\x08\x65lection\"%\n\x0f\x45lectionRequest\x12\x12\n\nprocess_id\x18\x01 \x01(\x05\"H\n\x10\x45lectionResponse\x12\x19\n\x11\x65lected_leader_id\x18\x01 \x01(\x05\x12\x19\n\x11\x65lection_messages\x18\x02 \x01(\x05\x32\xf3\x01\n\x08\x45lection\x12I\n\x10InitiateElection\x12\x19.election.ElectionRequest\x1a\x1a.election.ElectionResponse\x12J\n\x11RespondToElection\x12\x19.election.ElectionRequest\x1a\x1a.election.ElectionResponse\x12P\n\x17\x43oordinatorAnnouncement\x12\x19.election.ElectionRequest\x1a\x1a.election.ElectionResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'election_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_ELECTIONREQUEST']._serialized_start=28
  _globals['_ELECTIONREQUEST']._serialized_end=65
  _globals['_ELECTIONRESPONSE']._serialized_start=67
  _globals['_ELECTIONRESPONSE']._serialized_end=139
  _globals['_ELECTION']._serialized_start=142
  _globals['_ELECTION']._serialized_end=385
# @@protoc_insertion_point(module_scope)
