with Ada.Text_IO;
with Libhello;

procedure Purifierproof is
begin
   Libhello.Hello_World;
   Ada.Text_IO.Put_Line ("42");
end Purifierproof;
