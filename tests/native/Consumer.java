import java.lang.foreign.*;
import java.lang.invoke.*;
import java.nio.file.*;
public class Consumer {
  public static void main(String[] args) throws Throwable {
    Path expected = Path.of(args[0]).toRealPath();
    Arena arena = Arena.global();
    Linker linker = Linker.nativeLinker();
    SymbolLookup library = SymbolLookup.libraryLookup(expected, arena);
    MemorySegment symbol = library.find("purifier_answer").orElseThrow();
    MethodHandle call = linker.downcallHandle(symbol, FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.JAVA_INT));
    if ((int)call.invokeExact(0) != 42 || (int)call.invokeExact(1) != 43) throw new AssertionError("values");
    MemorySegment info = arena.allocate(4 * ValueLayout.ADDRESS.byteSize(), ValueLayout.ADDRESS.byteAlignment());
    MethodHandle origin = linker.downcallHandle(linker.defaultLookup().find("dladdr").orElseThrow(), FunctionDescriptor.of(ValueLayout.JAVA_INT, ValueLayout.ADDRESS, ValueLayout.ADDRESS));
    if ((int)origin.invokeExact(symbol, info) == 0) throw new AssertionError("dladdr");
    if (!Path.of(info.get(ValueLayout.ADDRESS, 0).reinterpret(4096).getString(0)).toRealPath().equals(expected)) throw new AssertionError("origin");
    Files.write(Path.of(args[1]), Files.readAllLines(Path.of("/proc/self/maps")).stream()
      .filter(line -> line.contains("/nix/store/"))
      .map(line -> line.substring(line.indexOf("/nix/store/")))
      .distinct().sorted().toList());
    System.out.println("Java 42/43 and exact library origin");
  }
}
