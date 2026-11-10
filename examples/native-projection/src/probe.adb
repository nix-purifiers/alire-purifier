with Libhello;
with Ada.Finalization;
with Ada.Text_IO;
package body Probe is
   use type Interfaces.C.int;
   type Lifetime is new Ada.Finalization.Limited_Controlled with null record;
   overriding procedure Finalize (Object : in out Lifetime);
   overriding procedure Finalize (Object : in out Lifetime) is
   begin
      Ada.Text_IO.Put_Line ("purifier finalized");
   end Finalize;
   Guard : Lifetime;
   Value : Interfaces.C.int := 0;
   function Answer (Offset : Interfaces.C.int) return Interfaces.C.int is (Value + Offset);
begin
   Libhello.Hello_World;
   Value := 42;
end Probe;
