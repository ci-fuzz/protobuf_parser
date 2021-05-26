#include <cstddef>
#include <cstdint>
#include <src/libfuzzer/libfuzzer_macro.h>

#include "pkg/web_app/grpc_driver/example/greeter.pb.h"

namespace {
const char *methods[] = {
    "/helloworld.Greeter/SayHello",
};

constexpr size_t kNumMethods = sizeof(methods) / sizeof(methods[0]);
}

extern "C" const char *proto_stub_get_method(uint32_t index) {
  return methods[index % kNumMethods];
}

extern "C" size_t proto_stub_mutate(uint32_t index, uint8_t* data, size_t size, size_t max_size, uint32_t seed) {
  uint32_t fixed_index = index % kNumMethods;
  switch (fixed_index) {
    case 0: {
      helloworld::HelloRequest message;
      return protobuf_mutator::libfuzzer::CustomProtoMutator(true, data, size, max_size, seed, &message);
    }
  }
  abort();
}
