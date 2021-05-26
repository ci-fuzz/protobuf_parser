import argparse
from pathlib import Path
from proto_parser import ProtoFile
from subprocess import run

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
    print(stub_cpp)


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