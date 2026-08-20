# Persona B Windows retest

On the same Windows machine that found the checkout blocker, use Windows
PowerShell 5.1 and perform only this retest:

1. Run the ordinary `git clone` commands in
   [Windows PowerShell 5.1](../README.md#windows-powershell-51). Do not use
   `-c core.autocrlf=false` or change the machine's existing Git setting.
2. Install with the documented PowerShell command.
3. Run the documented Set 001 and Set 002 qualification loop.
4. Run the documented one-byte tamper demonstration against its copied Set 001
   candidate.
5. Report only:
   - qualification: PASS or FAIL;
   - exact first friction point, if any;
   - whether the tamper failure was understandable; and
   - whether any command still felt Unix-specific.

Please include the `wexp-ref commit` and `wexp-vectors commit` lines printed by
the metadata commands. Do not send internal project history.
