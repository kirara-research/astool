This is a tool used to help extract the master keys from an il2cpp memory dump.

It can find the base of the il2cpp image in the memory dump, as well as locate the
Constant .cctor within the image.

It uses Capstone to show the disassembly so you will need that library installed.
