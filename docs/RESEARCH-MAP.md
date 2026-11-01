# Keshav paper-reading map

`study-content/keshav-reading-map.json` captures a local, evidence-linked reading of the three-page `HowtoReadPaper.pdf`. It is loaded into the research graph with `scripts/load_research_map.py`.

## Scope and evidence rules

The map follows the paper’s own three-pass method and its literature-survey section. Every method node has a PDF page/section locator and a short quotation. The five entries in the paper’s References section are represented as **listed references** only. Their graph edges say “lists reference”; the map does not assess their contents or infer the learner’s reading history, and does not claim that citation means scientific influence, agreement, or dependency.

No other papers, results, or assumptions have been attributed to those references. “Challenge assumptions” records Keshav’s advice for reading a target paper, not a claim that Keshav’s methodological article itself contains a scientific derivation or experiment.

## Load or refresh

Start the local API and run from the repository root:

```powershell
.venv/Scripts/python scripts/load_research_map.py --dry-run
.venv/Scripts/python scripts/load_research_map.py
```

The loader registers the PDF by its existing local path if the source is absent. Set `--pdf` to another local copy if needed. It uses a stable `content_key` on the source, nodes, and edges, so reruns update the same graph records instead of adding duplicates. It makes no agent/model or web-research calls.

The default PDF path is specific to this workstation. The source is user-owned and is not copied into this repository.
