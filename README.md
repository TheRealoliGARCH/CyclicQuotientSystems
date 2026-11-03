# Cyclic Quotient Systems

This repository contains the mathematical foundations, noisy extensions, and empirical applications of Cyclic Quotient Systems (CQS). The empirical paper is reproducible from one Python 3 entry point and one GitHub Actions workflow.

## Repository contents

- The three existing PDF treatises (items 1–3) provide the theoretical and earlier empirical foundations.
- `src/empirical_g20_cqs.py` is the earlier G20 illustration.
- `scripts/generate_empirical_paper.py` downloads the 60-country panel, writes data audits, and generates the new paper.
- `.github/workflows/generate-empirical-paper.yml` is the single workflow for paper generation.
- `data/processed/` contains the generated raw-indicator snapshot, panel, and coverage audit.
- The generated paper is saved in the repository root as:
  `4. A Cross-Country Statistical and Econometric Analysis of Structural Relationships, Long-Run Dynamics, and Error Correction Using Cyclic Quotient Systems.pdf`

## Sample and variables

The fixed 60-country panel is encoded in the Python script. The seven variables are population, land area, population density (derived), Gini index, real GDP per capita (constant 2015 US dollars), total real GDP (constant 2015 US dollars), and general government final consumption expenditure (% GDP).

Six observed World Bank WDI indicators are used: `SP.POP.TOTL`, `AG.LND.TOTL.K2`, `SI.POV.GINI`, `NY.GDP.PCAP.KD`, `NY.GDP.MKTP.KD`, and `NE.CON.GOVT.ZS`. The last is general government final consumption expenditure, not total government expenditure. Population density is derived from population and land area; thus the design has six observed indicators and one derived variable.

## Reproduce locally

Requires Python 3.11+, pandas, requests, and reportlab.

```bash
python -m pip install pandas requests reportlab
python scripts/generate_empirical_paper.py --start 2000 --end 2025
```

The script writes `data/processed/world_bank_indicators_long.csv`, `country_year_panel.csv`, and `variable_coverage.csv`, then renders the PDF in the repository root. Missing observations are retained; Gini values are not interpolated. Future World Bank revisions can change subsequent snapshots.

## GitHub Actions

Run **Generate CQS Empirical Paper** from the Actions tab, or let it run when the generator/workflow changes on `main`. The workflow installs the same dependencies, executes the same script, and commits the PDF and data snapshot when outputs change. The implementation is Python-only and requires no R runtime or package.

## Interpretation and econometric cautions

For positive levels on a closed cycle, successive quotients telescope to one. This is an algebraic identity, not evidence of an economic relationship, cointegration, or causality. A noisy-cycle test requires independently measured edge quantities and an explicit joint measurement-error covariance model.

The candidate pair of log real GDP per capita and government final-consumption share remains provisional. Earlier Engle-Granger results were weak and specification-sensitive. A single exploratory Westerlund-style group-mean Gt rejection does not establish stable panel-wide cointegration; the custom Python implementation and synchronized block bootstrap are not claimed to be bit-for-bit equivalent to a canonical reference implementation. Preliminary Monte Carlo calibration showed selected null-size distortions, so equation-level verification and larger simulations remain necessary.

Population density is mechanically derived; GDP per capita multiplied by population is a consistency diagnostic, not an exact independent identity with total GDP; Gini coverage is sparse and survey-method dependent; and government final consumption is narrower than total public expenditure. Cross-sectional dependence, structural breaks, heterogeneous slopes, short time dimension, and data revisions further constrain inference.

## License

See `LICENSE` for the repository's license terms.
