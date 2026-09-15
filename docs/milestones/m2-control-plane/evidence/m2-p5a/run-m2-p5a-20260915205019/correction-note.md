# M2-P5A RED hardening correction

This new run corrects the five frozen P5A RED oracles to pass an explicit active P1 `SqlUnitOfWork.connection` or UoW-bound adapter for every durable operation. It also uses an independent all-field revision snapshot, behavioral migration constraint probes, and the accepted P2 `request_hash` canonicalizer.

No production implementation, migration `0004`, P5B/P6+/M3/Module A, or previously accepted correction run was changed. The exact five testcase identities remain frozen. The final lifecycle remains `M2-P5A_RED_READY_FOR_REVIEW`; independent audit is still required.
