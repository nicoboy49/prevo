# How Prévo is built

*Version française : [METHODE.fr.md](METHODE.fr.md)*

Prévo is a free, open source maintenance management system (CMMS) for small industrial companies. Its author, Nicolas Briand, is a maintenance technician turned trainer; it is published with SELECTIS (<https://selectis.eu>). Prévo was not typed by a person: it was written by AI agents (Claude Code) under the direction of a human who decides and validates. This page explains how that works in practice, for anyone wondering whether software built by AI can be controlled. It is a summary; the detailed account, in French, is [PILOTAGE.md](PILOTAGE.md).

## 1. Write down what is expected before any code

Three documents come before the first line of code:

- a **requirements brief**, written by Nicolas Briand with Claude: needs, screens, tables, business rules, a split into work packages ("lots");
- a **project specification** that turns the brief into commitments, validated by Nicolas before any code. For the first lot: 18 decisions and 20 measurable success criteria;
- an **architecture contract** (`docs/ARCHITECTURE.md`): file formats, the schema of the 22 tables, module interfaces, business rules. Every agent receives it, so files written separately fit together.

Decisions that commit the user stay with the human. The AI proposes them, with their consequences.

## 2. Tasks, waves, and a tool that checks each wave

The work is cut into small tasks grouped in **waves**: tasks in one wave do not depend on each other and run in parallel. The first lot was 19 tasks in 7 waves. One session, the **orchestrator**, does not write the code: it frames the tasks, hands them to **sub-agents** (each gets a precise brief: allowed files, forbidden files, a verification command), then checks and decides.

The rule that matters most: **a task is accepted only if its verification command passes when the orchestrator runs it again itself.** A sub-agent's report is never enough, because it can be wrong or conclude too early. At the end of each wave, a **reviewer who did not write the code** reads it looking for defects. Each task is one commit tagged with its number; each validated wave, and each finished lot, has a git tag (`lot-1` to `lot-7`, then `v1.0.0` to `v1.2.1` and `v2.0.0-beta.1`, `-beta.2`).

## 3. Tests first, the full suite before every release

A defect is fixed only after it has been **reproduced by a test that fails**; the test then passes with the fix and stays in the suite. End-to-end scenarios run in a real browser (Chromium), in server mode and in demo mode. Before a publication, the complete suite is run in one go. Tests never use real company data, and no real AI model is used inside the suite: a fake provider makes tests fast, repeatable, and able to simulate failures.

## 4. Where the human stops the process

The human validates: the requirements and every product decision; security-related choices; each publication (tags and releases are pushed only after his agreement); and everything an AI cannot check alone, such as a real shared folder, a real phone, a printed work order, or an installation on a PC without Python. These checks are listed as planned until he reports their result.

## 5. Defects this discipline found

- **Data loss on a damaged file.** If a data file was damaged outside Prévo (a note typed in Excel, a missing quote), the application could rewrite it and lose what it could not read. Version 1.2.1 and 2.0.0 beta 2 fix it: a damaged file is never rewritten, a "Damaged file" banner appears, and the user's input stays in the form. Beta 1 was affected, which the README says openly.
- **Lot 1 reviews:** 5 critical defects, all fixed before moving on, among them two possible data losses when another PC writes at the same moment, and a work-order closing rule that could be bypassed from two PCs at once.
- **Installation (lot 7):** found while writing the install guide and by a server-mode acceptance run that follows the user's path: a release zip missing the entry page, a dead end at the first account (nobody could log in, setup included), and the certificate's private key leaking into backups.
- **Wiki (lot 6):** the review log counts about fifty defects classed critical, all fixed before the next wave, for example profiles seeing information they should not.

## 6. What the method does not guarantee

- Green tests show that the cases written pass, not that no other defect exists. Independent review reduces this risk without removing it.
- Performance figures come from one machine and one data set.
- Some checks only real equipment can give (phones, a remote connection, a real network). They go through acceptance runs by the human, and their results are recorded only once done.
- 2.0.0 and 2.1.0 have just been released: they have not yet been proven in the field for long. Version 1.2.1 remains available.

## 7. Figures

| Figure | Value | Source |
|---|---|---|
| Commits in the repository | 529, from 2026-10-19 to 2026-11-08 | `git rev-list --count v2.1.0` |
| Lot tags | 14 (`lot-1` to `lot-7`, `lot-3-bis`; `lot-i18n-1` to `lot-i18n-6` for the multilingual work) | `git tag` |
| Tests at the end of lot 1 | 411 | PILOTAGE.md §4 |
| Tests at the end of lot 7 | 1,762 (full run: 39 minutes) | PILOTAGE.md §13 |
| Last complete suite | 2,362 tests in 158 files, on 2.1.0 | complete run of 2026-11-08 |
| Releases | 1.0.0 (2026-10-21), 1.1.0 (2026-10-22), 1.2.0 (2026-10-24 per CHANGELOG), 1.2.1 (2026-11-04), 2.0.0 beta 1 (2026-10-28), beta 2 (2026-11-05), 2.0.0 (2026-11-08), 2.1.0 (2026-11-08) | CHANGELOG.md, git tags |
| Lot 1 organisation | 19 tasks, 7 waves, 4 reviews, 5 critical defects | PILOTAGE.md §2 and §3 |
| Lot 7 organisation | 33 tasks in 12 waves, 45 commits | PILOTAGE.md §13 |
| Dependencies added in lot 7 | none | PILOTAGE.md §13 |
| Time, first seven days (2026-10-19 to 10-25, up to 1.2.0) | 84 h of active Claude Code sessions (autonomous nights included), plus 10 h of design in chat | making-of page |
| Cost, same period | €90 at most (Claude Max subscription for one month, shared with other projects); €1,674 if the same calls had been billed at the public API price | making-of page |
| AI usage, same period | 4.66 billion tokens over 14,708 calls (98% cache reads) | making-of page |

These time and cost figures are minimums (design in chat is not counted in tokens) and do not include the 2.0 work. Source: [Création de Prevo](https://selectis.eu/ia/creation-de-prevo.html) (in French, page of 25 October 2026).


## 8. Five points to keep

1. Have the requirements and success criteria written and validated before the code.
2. Write the contract between the parts before distributing the work.
3. Accept a task on evidence you rerun yourself, never on a statement.
4. Have it reviewed by someone who did not write the code, and reproduce each defect with a test before fixing it.
5. Keep decisions for the human, and ask him for the physical checks.

The full list (eleven points) is in section 14 of [PILOTAGE.md](PILOTAGE.md).

---

*Figures dated 2026-11-08 (Prévo 2.1.0). More detail, in French: [PILOTAGE.md](PILOTAGE.md). Project: <https://github.com/nicoboy49/prevo>.*
