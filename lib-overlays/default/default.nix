final: prev: {
  alire-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
