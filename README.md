# alire-purifier

Locked, Nix-built Ada dependencies for Alire.

## Quickstart

```sh
nix shell 'github:nix-purifiers/alire-purifier'
alire-purifier lock
alr build
alr run
```

Alire's native resolver selects the dependencies from `alire.toml`. Nix fetches
those revisions, generates their native configurations, builds them and installs
their GPR projects. Your project builds in its working tree.

Commit `alire-purifier.lock.json`. Source edits do not require relocking. Change
the native manifest and update the lock to select other dependencies:

```sh
alire-purifier lock --update
```

The shell provides Alire, GNAT and GPR tools. Wrappers without a lockfile warn and
run the ordinary, impure tools. Invalid or stale locks fail. The integration can
also be installed through your normal Nix configuration.

## Development

Alire sees the compiled dependencies as native external packages. Their versions
and dependency constraints remain in its solution, and their GPR projects point
at readonly Nix sources and libraries. Private Alire settings and native project
metadata keep the working-tree build mutable.

```sh
alr clean
alr printenv
alire-purifier exec -- your-editor
```

GNAT and GPR-based editors use the same native project environment. Root project
commands retain their ordinary network access.

```sh
alire-purifier prefetch
```

`--input path` tracks additional selection files. Use `--project` and `--lock` for
an external companion; native wrappers accept `ALIRE_PURIFIER_PROJECT` and
`ALIRE_PURIFIER_LOCK`. Environment generations retain their dependency and SDK
closures for garbage collection.

The initial integration targets Linux with Alire 2.1.1, GNAT 16.2 and GPRbuild 25.
It supports exact Git source origins. Architecture-dependent dependency selection
and external system packages need additional integration. The SDK supplies the
compiler and build tools. Dependency selection and index changes go through lock
updates; ordinary build, run and inspection commands use the prepared solution.

## Publication

```sh
alire-purifier bundle
alire-purifier publish --tag v0.1.0
```

The reproducible source archive contains native Alire and GPR metadata. Ordinary
Alire can consume it. Publication uploads the exact realized bytes to an existing
GitHub release.

## Building with Nix

An optional definition can use the overlay's named builder:

```nix
pkgs.alire-purifier.buildAlireProject {
  src = ./.;
}
```

It exposes evaluation-known `packages`, `tests`, `release` and `fetches`.
`libraryOverrides` supplies crate-specific build changes.

### Native C ABI projections

Opt in to installed shared libraries with an explicit owning GPR project, public
C headers, exports, and runtime contract:

```nix
pkgs.alire-purifier.buildAlireProject {
  src = ./.;
  nativeLibraries.answer = {
    project = "purifierprobe.gpr";
    library = "lib/purifierprobe/libpurifier_probe.so";
    headers = [ "purifier_probe.h" ];
    exports = [ "purifier_answer" ];
    runtime = {
      kind = "gnat";
      initialization = "linker-constructor";
      lifecycle = "process-lifetime";
      threading = "single-foreign-thread";
    };
  };
}
```

`library` selects a file in the native `gprinstall` prefix. Header paths are
relative to the source project and keep their relative paths under `include`.
The GPR project must produce a standalone shared library with automatic
elaboration and finalization, for example `Library_Standalone = "standard"`
and `Library_Auto_Init = "true"`. Public Ada subprograms need a C convention and
explicit exported names matching the owned C header. Configure PIC/shared
dependencies through their native GPR scenario variables before capturing the
lock, such as `LIBHELLO_LIBRARY_TYPE=relocatable alire-purifier lock`.

The result exposes `native` and `projections.native`, `projections.python-ffi`,
and `projections.java-ffi`. The native catalog identifies the selected library
prefix; the Python adapter provides `purifier_native.load("answer")`. Java's
`java.args` configures the projected native paths and catalog for ordinary FFI
consumers. The adapter does not infer C function signatures.

Libraries retain their installed bytes and original Nix runtime dependencies.
Selection verifies the native installation manifest, declared exports, compiled
library identity, and generated binder constructor/destructor. The retained
`native-libraries.json` records compiler, headers, binder and isolated-loader
origins. An existing host process can already have a compatible GCC support
library loaded; its actual origin can differ from isolated `ldd`. Consumer
proofs separately record actual loaded libraries and require exact origins for
the GNAT runtime and locked Ada dependency.

This interface currently requires native Linux builds. Keep the library loaded
for the process lifetime, call it from one foreign thread, and let its linker
constructor/destructor manage Ada elaboration/finalization. Manual runtime
entry calls, early unload, concurrent calls, and exceptions crossing the C ABI
are outside this contract. Empty `nativeLibraries` preserves existing outputs.
Source publication remains a native Alire source archive.

The native checks execute C, ctypes, CFFI and Java FFI consumers, including
automatic elaboration/finalization, byte and runtime-origin checks, genuine
compiled replacement and missing-closure controls, fresh native resolver
capture, and direct producer/projection/consumer rebuilds. Volatile GPR
incremental caches are pruned after retaining their semantic exchange sections;
native binder source and compiled library bytes remain unchanged.

## Credits

The purifier idea was inspired by nixcloud's
[cargo (libnix)](https://github.com/nixcloud/cargo).
