# Data licence

The code in this repository is Apache 2.0 (`LICENSE`). The data is not.

Everything under `reference/` is derived from the Hull Domesday Project's database — the
geocoded, coded Domesday of Professor J.J.N. Palmer and his team at the University of Hull,
published as the Domesday Explorer — and is licensed, as Hull licenses it, under
**Creative Commons Attribution-NonCommercial-ShareAlike** (CC BY-NC-SA).

- **Attribution:** Professor J.J.N. Palmer, George Slater and the University of Hull.
- **NonCommercial:** use it for anything that is not primarily for commercial advantage.
- **ShareAlike:** anything you build from this data carries the same licence.

The source is the Hull Domesday Project's own deposit: <https://digitalcollections.hull.ac.uk/collections/3t945r28b>.
The tables this realm reads come from the Explorer's v1.1 update, published by the project at
<https://www.domesdaybook.net/downloads>.

**What is not here.** The Explorer's text store holds the Phillimore translation of Domesday
word for word. That translation is Phillimore's, not Hull's, and this realm does not republish
it: `scripts/build_reference.py` reads the coded clauses to parse the figures and writes none of
the text.
