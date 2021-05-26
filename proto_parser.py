from enum import Enum
from io import StringIO
from typing import List, TextIO, IO, Dict, Any

import argparse
from pathlib import Path
from subprocess import run

WORD_SERVICE = "service"
WORD_RPC = "rpc"
WORD_MESSAGE = "message"
WORD_ENUM = "enum"
WORD_OPTION = "option"
WORD_BODY = "body"
WORD_ROOT = "root"
WORD_FIELD = "field"
WORD_PROTO_FILE = "proto_file"
WORD_REPEATED = "repeated"


class HttpMethod(Enum):
    UNKNOWN = ""
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"


VALID_HTTP_METHODS = {
    "get": HttpMethod.GET,
    "post": HttpMethod.POST,
    "put": HttpMethod.PUT,
    "patch": HttpMethod.PATCH,
    "delete": HttpMethod.DELETE
}

DeclarationDict = Dict[str, List]


class ScopedSection:
    def __init__(self, name: str = "", data_type: str = "", declaration_dict: DeclarationDict = None):
        if declaration_dict is None:
            declaration_dict = {
            }

        self.declaration_dict: DeclarationDict = declaration_dict
        self.data_type: str = data_type
        self.name: str = name

    def add(self, obj_type: str, obj: Any):
        self.declaration_dict[obj_type].append(obj)

    def __eq__(self, other):
        if self.name != other.name or self.data_type != other.data_type:
            return False
        for scope_key in self.declaration_dict.keys():
            if self.declaration_dict[scope_key] != other.declaration_dict[scope_key]:
                return False
        return True


class MessageField:
    def __init__(self, name: str = "", data_type: str = "", is_array: bool = False):
        self.name: str = name
        self.data_type: str = data_type
        self.is_array: bool = is_array

    def __eq__(self, other):
        return self.name == other.name and self.data_type == other.data_type and self.is_array == other.is_array


class ProtoEnum:
    def __init__(self, name: str = "", values: List[str] = None):
        if values is None:
            values = []
        self.name: str = name
        self.values: List[str] = values

    def __eq__(self, other):
        return self.values == other.values and self.name == other.name


class Message(ScopedSection):
    def __init__(self, name: str = "", declaration_dict: DeclarationDict = None):
        super().__init__(name=name, data_type=WORD_MESSAGE, declaration_dict=declaration_dict)

    def __eq__(self, other):
        if self.declaration_dict != other.declaration_dict:
            return False
        if self.data_type != other.data_type:
            return False
        if self.name != other.name:
            return False

        for scope_key in self.declaration_dict.keys():
            if self.declaration_dict[scope_key] != other.declaration_dict[scope_key]:
                return False
        return True


class RPC:
    def __init__(self, name: str = "", req: str = "", resp: str = "",
                 endpoint: str = "", http_method: HttpMethod = HttpMethod.UNKNOWN):
        self.name: str = name
        self.request: str = req
        self.response: str = resp
        self.endpoint: str = endpoint
        self.http_method: HttpMethod = http_method

    def __eq__(self, other):
        return self.name == other.name and self.response == other.response and \
               self.request == other.request and self.endpoint == other.endpoint and \
               self.http_method == other.http_method


class Service:
    def __init__(self, name: str = "", rpc_list: List[RPC] = None):
        if rpc_list is None:
            rpc_list = []
        self.name: str = name
        self.rpc_list: List[RPC] = rpc_list

    def __eq__(self, other):
        return self.name == other.name and self.rpc_list == other.rpc_list


class ProtoFile(ScopedSection):
    def __init__(self):
        super().__init__(WORD_ROOT)
        self.root_scope: ScopedSection = ScopedSection()

    @staticmethod
    def get_wraped_text(lines: List[str], start_idx: int = -1) -> List[str]:
        count_ = 0
        segments = []
        found = False
        j = start_idx
        while True:
            segment = ""
            while j < len(lines) - 1:
                j += 1
                line = lines[j].strip()
                line = line.replace("  ", " ").replace("\t", " ")
                # if a blank line
                if line.replace("\n", "").replace("\r", "") == "":
                    continue
                # if is a comment
                if line.startswith("//"):
                    continue
                if line.count("{"):
                    count_ += 1
                    found = True
                if line.count("}"):
                    count_ -= 1
                if found:
                    segment += line + "\n"
                    if count_ < 1:
                        break
            if segment == "":
                break
            found = False
            count_ = 0
            segments.append(segment)
        return segments

    @staticmethod
    def extract_type_name_from_line(line: str) -> str:
        """ i.e: if line == "message UpdateBasketReq {"
         return "UpdateBasketReq":
         """
        name_line = line.strip().split()
        if len(name_line) < 2:
            raise ValueError("invalid line: " + line[0])
        return name_line[1].replace("{", "").replace("}", "")

    @staticmethod
    def extract_enum(lines: List[str]) -> (ProtoEnum, int):
        enum = ProtoEnum()
        enum.name = ProtoFile.extract_type_name_from_line(lines[0])
        out_idx = 1
        for i in range(1, len(lines) - 1):
            out_idx += 1
            line_sp = lines[i].replace("=", " ").strip().split()
            if line_sp[0] == "}":
                break
            if len(line_sp) < 2:
                raise ValueError("invalid enum value" + lines[i])
            enum.values.append(line_sp[0])
        return enum, out_idx

    @staticmethod
    def extract_service(lines: List[str]) -> (Service, int):
        out_idx = 1
        service = Service()
        service.name = ProtoFile.extract_type_name_from_line(lines[0])
        if len(lines) < 2:
            raise ValueError("empty service: " + service.name)
        service_blocks = ProtoFile.get_wraped_text(lines, 0)
        for block in service_blocks:
            block_lines = block.splitlines()
            rpc = RPC()
            for i in range(0, len(block_lines)):
                out_idx += 1
                block_lines[i] = block_lines[i].strip()
                if block_lines[i] == "":
                    continue
                if block_lines[i].startswith(WORD_RPC):
                    arr = block_lines[i].replace("(", " ").replace(")", " ").strip().split()
                    rpc.name = arr[1]
                    rpc.request = arr[2]
                    rpc.response = arr[4]
                    if len(block_lines) == 1:
                        service.rpc_list.append(rpc)
                    continue
                if block_lines[i].startswith(WORD_OPTION):
                    continue
                block_lines_sp = block_lines[i].split()
                if len(block_lines_sp) < 1:
                    raise ValueError("unexpected: " + block_lines[i])
                init = block_lines_sp[0].replace(":", "")
                if init in VALID_HTTP_METHODS.keys():
                    rpc.http_method = VALID_HTTP_METHODS[init]
                    rpc.endpoint = block_lines_sp[1].replace("\"", "")
                    continue
                if init == WORD_BODY:
                    continue
                if rpc.name == "":
                    continue
                service.rpc_list.append(rpc)
                break
        return service, out_idx

    @staticmethod
    def extract_field_from_line(line: str) -> MessageField:
        line_sp = line.strip().split()
        if len(line_sp) < 2:
            raise ValueError("invalid field line:" + line)
        field = MessageField()
        if line_sp[0] == WORD_REPEATED:
            field.is_array = True
            line_sp = line_sp[1:]
        field.data_type = line_sp[0]
        field.name = line_sp[1]
        return field

    @staticmethod
    def omitline(line: str) -> bool:
        line_type_strip = line.strip().split()
        if len(line_type_strip) == 0:
            return True
        line = line_type_strip[0].strip().replace(";", "").replace("{", "").replace("}", "")
        return line in ["", "//", "import", "option", "syntax", "package"]

    @staticmethod
    def add_to_dict(d: Dict[str, List], key, val):
        if key not in d:
            d[key] = []
        d[key].append(val)

    @staticmethod
    def find_the_end_of_scope(lines: List[str]) -> int:
        offset = 0
        i = 0
        found = False
        while i < len(lines):
            offset += lines[i].count("{")
            if lines[i].count("{") > 0:
                found = True
            offset -= lines[i].count("}")
            i += 1
            if offset < 1 and found:
                break
        return i

    @staticmethod
    def extract_scope(lines: List[str], sc: ScopedSection, start_idx=0) -> (ScopedSection, int):
        if lines is None or len(lines) == 0:
            raise ValueError("empty lines")
        i = -1
        while i < len(lines):
            i += 1
            if i >= len(lines):
                break
            finish_idx = 0
            lines[i] = lines[i].strip()
            if lines[i].startswith(WORD_MESSAGE):
                field = ProtoFile.extract_field_from_line(lines[i])
                parent = Message()
                end_idx = ProtoFile.find_the_end_of_scope(lines[i:])
                # Recursion
                msg, finish_idx = ProtoFile.extract_scope(lines[i + 1:i + end_idx], parent)
                msg.name = field.name
                msg.data_type = field.data_type
                ProtoFile.add_to_dict(sc.declaration_dict, WORD_MESSAGE, msg)
            elif lines[i].startswith(WORD_ENUM):
                enum, finish_idx = ProtoFile.extract_enum(lines[i:])
                ProtoFile.add_to_dict(sc.declaration_dict, WORD_ENUM, enum)
            elif lines[i].startswith(WORD_SERVICE):
                service, finish_idx = ProtoFile.extract_service(lines[i:])
                ProtoFile.add_to_dict(sc.declaration_dict, WORD_SERVICE, service)
            else:
                if not ProtoFile.omitline(lines[i]):
                    field = ProtoFile.extract_field_from_line(lines[i])
                    if field.name != "":
                        ProtoFile.add_to_dict(sc.declaration_dict, WORD_FIELD, field)
            i += finish_idx
        return sc, i

    @staticmethod
    def parse_file(file_path: str) -> ScopedSection:
        with open(file_path) as f:
            lines = f.read().splitlines()
            root = ScopedSection(name=WORD_ROOT, data_type=WORD_PROTO_FILE)
            result, _ = ProtoFile.extract_scope(lines, root)
        return result


def parse_protobuf(input_file):
    proto = ProtoFile()
    result = proto.parse_file(input_file)

    # usally we only have one service name, but it can have multiple rpcs
    for service in result.declaration_dict["service"]:
        rpcs = []
        for rpc in service.rpc_list:
            rpcs.append({"service":service.name, "rpc": rpc.name, "request":rpc.request})
    # for message in result.declaration_dict["message"]:
    #     if message.name in requests:
    #         for field in message.declaration_dict["field"]:
    #             print(field.name)

    return rpcs


def proto_stub_cpp_generator(rpcs, PROTO_OUT, protobuf_file):
    stub_cpp_template = """#include <cstddef>
#include <cstdint>
#include <src/libfuzzer/libfuzzer_macro.h>

#include "{}"

namespace {{
const char *methods[] = {{
    {}
}};

constexpr size_t kNumMethods = sizeof(methods) / sizeof(methods[0]);
}}

extern "C" const char *proto_stub_get_method(uint32_t index) {{
  return methods[index % kNumMethods];
}}

extern "C" size_t proto_stub_mutate(uint32_t index, uint8_t* data, size_t size, size_t max_size, uint32_t seed) {{
  uint32_t fixed_index = index % kNumMethods;
  switch (fixed_index) {{
    {}}}
  abort();
}}"""
    protobuf_basename = protobuf_file.split(".")[0]

    PROTO_OUT = "pkg/web_app/grpc_driver/example"
    include = "{}/{}.pb.h".format(PROTO_OUT, protobuf_basename)
    include = "pkg/web_app/grpc_driver/example/greeter.pb.h"

    namespace_methods = ""
    switch_cases = ""
    for count, rpc in enumerate(rpcs):
        namespace_methods += """"/{}.{}/{}",""".format(protobuf_basename, rpc["service"], rpc["rpc"])

        switch_cases += """case {}: {{
      {}::{} message;
      return protobuf_mutator::libfuzzer::CustomProtoMutator(true, data, size, max_size, seed, &message);
    }}\n  """.format(count, protobuf_basename, rpc["request"])

    stub_cpp = stub_cpp_template.format(include, namespace_methods, switch_cases)


def compile_protobuf(PROTOC_BIN, PROTO_OUT, input_file):
    path = Path(input_file)
    run([PROTOC_BIN, "-I", path.parent.absolute(), path.absolute(), "--cpp_out={}".format(PROTO_OUT)])


def main():
    PROTOC_BIN = "/home/roman/projects/yandex/grpc-java/protoc-3.17.0/bin/protoc"
    PROTO_OUT = "."

    parser = argparse.ArgumentParser(description='Parse Protobuf description')
    parser.add_argument("protbuf_file")
    args = parser.parse_args()
    protobuf_file = args.protbuf_file
    rpcs = parse_protobuf(protobuf_file)

    compile_protobuf(PROTOC_BIN, PROTO_OUT, protobuf_file)

    # rpcs format [{"service":"Greeter", "rpc":"SayHello", "request":"HelloRequest"}]
    proto_stub_cpp_generator(rpcs, PROTO_OUT, protobuf_file)


if __name__ == "__main__":
    main()