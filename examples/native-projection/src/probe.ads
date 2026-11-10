with Interfaces.C;
package Probe is
   function Answer (Offset : Interfaces.C.int) return Interfaces.C.int;
   pragma Export (C, Answer, "purifier_answer");
end Probe;
