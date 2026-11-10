#define _GNU_SOURCE
#include "purifier_probe.h"
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
  assert(argc == 3);
  void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
  if (!library) { puts(dlerror()); return 1; }
  __typeof__(purifier_answer) *answer = dlsym(library, "purifier_answer");
  assert(answer && answer(0) == 42 && answer(1) == 43);
  Dl_info info; assert(dladdr(answer, &info));
  char *actual = realpath(info.dli_fname, NULL), *expected = realpath(argv[1], NULL);
  assert(actual && expected && strcmp(actual, expected) == 0);
  free(actual); free(expected);
  FILE *maps = fopen("/proc/self/maps", "r"), *record = fopen(argv[2], "w");
  assert(maps && record);
  char line[16384];
  while (fgets(line, sizeof(line), maps)) {
    char *path = strstr(line, "/nix/store/");
    if (path) assert(fputs(path, record) >= 0);
  }
  assert(fclose(maps) == 0 && fclose(record) == 0);
  puts("C 42/43 and exact library origin");
  /* The declared contract retains the library until natural process exit. */
}
