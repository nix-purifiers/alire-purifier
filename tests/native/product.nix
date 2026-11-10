{
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
}
