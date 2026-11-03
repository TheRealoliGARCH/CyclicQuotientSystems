#!/usr/bin/env python3
"""Reproducibly acquire the CQS 60-country panel and render its empirical paper."""
import argparse, time
from pathlib import Path
import requests
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

TITLE = "A Cross-Country Statistical and Econometric Analysis of Structural Relationships, Long-Run Dynamics, and Error Correction Using Cyclic Quotient Systems"
AUTHORS = "Lord Soumadeep Ghosh with ChatGPT (OpenAI)"
PLACE = "Kolkata, India"
COUNTRIES = [
("Austria","AUT"),("Australia","AUS"),("Belgium","BEL"),("Canada","CAN"),("Switzerland","CHE"),
("China","CHN"),("Germany","DEU"),("Denmark","DNK"),("Spain","ESP"),("France","FRA"),
("Greece","GRC"),("Indonesia","IDN"),("Israel","ISR"),("India","IND"),("Italy","ITA"),
("Japan","JPN"),("North Korea","PRK"),("South Korea","KOR"),("Mexico","MEX"),
("The Netherlands","NLD"),("Pakistan","PAK"),("Portugal","PRT"),("Russia","RUS"),
("United Kingdom","GBR"),("United States","USA"),("Algeria","DZA"),("Argentina","ARG"),
("Armenia","ARM"),("Azerbaijan","AZE"),("Bahrain","BHR"),("Bhutan","BTN"),("Brazil","BRA"),
("Chile","CHL"),("Egypt","EGY"),("Finland","FIN"),("Ghana","GHA"),("Ireland","IRL"),
("Jordan","JOR"),("Kazakhstan","KAZ"),("Kenya","KEN"),("Kyrgyzstan","KGZ"),("Malaysia","MYS"),
("Morocco","MAR"),("Nigeria","NGA"),("Philippines","PHL"),("Poland","POL"),
("Saudi Arabia","SAU"),("Singapore","SGP"),("South Africa","ZAF"),("Sweden","SWE"),
("Afghanistan","AFG"),("Thailand","THA"),("Myanmar","MMR"),("Nepal","NPL"),
("Bangladesh","BGD"),("Sri Lanka","LKA"),("Maldives","MDV"),("Türkiye","TUR"),
("Vietnam","VNM"),("Ukraine","UKR")]
IND = {"population":"SP.POP.TOTL","land_area_km2":"AG.LND.TOTL.K2",
"gini_index":"SI.POV.GINI","real_gdp_per_capita_2015_usd":"NY.GDP.PCAP.KD",
"total_real_gdp_2015_usd":"NY.GDP.MKTP.KD",
"government_final_consumption_pct_gdp":"NE.CON.GOVT.ZS"}
PDF = "4. " + TITLE + ".pdf"

def get_series(session, iso, code, start, end):
    url=f"https://api.worldbank.org/v2/country/{iso}/indicator/{code}"
    for n in range(4):
        try:
            r=session.get(url,params={"date":f"{start}:{end}","format":"json","per_page":20000},timeout=45)
            r.raise_for_status(); j=r.json()
            return [{"iso3":iso,"year":int(x["date"]),"indicator":code,"value":x.get("value")}
                    for x in (j[1] or [])] if isinstance(j,list) and len(j)>1 else []
        except (requests.RequestException,ValueError):
            if n==3: raise
            time.sleep(n+1)

def acquire(start,end,out):
    s=requests.Session(); s.headers["User-Agent"]="CyclicQuotientSystems-reproducibility/1.0"
    rows=[]
    for _,iso in COUNTRIES:
        for _,code in IND.items(): rows.extend(get_series(s,iso,code,start,end))
    raw=pd.DataFrame(rows)
    if raw.empty: raise RuntimeError("World Bank API returned no observations")
    raw.to_csv(out/"world_bank_indicators_long.csv",index=False)
    p=raw.pivot_table(index=["iso3","year"],columns="indicator",values="value",aggfunc="first").reset_index()
    p.columns.name=None
    p=p.rename(columns={v:k for k,v in IND.items()})
    p["country"]=p.iso3.map({iso:name for name,iso in COUNTRIES})
    p["population_density_per_km2"]=p.population/p.land_area_km2
    p["implied_gdp_from_pc_population"]=p.real_gdp_per_capita_2015_usd*p.population
    p["gdp_consistency_ratio"]=p.implied_gdp_from_pc_population/p.total_real_gdp_2015_usd
    p=p.sort_values(["iso3","year"]); p.to_csv(out/"country_year_panel.csv",index=False)
    vars=list(IND)+["population_density_per_km2"]
    cov=pd.DataFrame([{"variable":v,"nonmissing":int(p[v].notna().sum()),
      "observations":len(p),"coverage_pct":100*p[v].notna().mean()} for v in vars])
    cov.to_csv(out/"variable_coverage.csv",index=False)
    return p,cov

def render(panel,cov,start,end,path):
    st=getSampleStyleSheet()
    st.add(ParagraphStyle(name="T",parent=st["Title"],fontSize=15,leading=19,alignment=TA_CENTER,spaceAfter=12))
    st.add(ParagraphStyle(name="A",parent=st["Normal"],alignment=TA_CENTER,spaceAfter=5))
    st.add(ParagraphStyle(name="B",parent=st["BodyText"],alignment=TA_JUSTIFY,leading=14,spaceAfter=7))
    def P(x): return Paragraph(x,st["B"])
    story=[Paragraph(TITLE,st["T"]),Paragraph(AUTHORS,st["A"]),Paragraph(PLACE,st["A"]),Spacer(1,12)]
    sections=[
("Abstract","This paper develops a reproducible cross-country statistical and econometric application of Cyclic Quotient Systems (CQS). It specifies graph-based quotient restrictions and a seven-variable panel for 60 economies over the selected period. Six World Bank indicators are observed and population density is derived. The paper distinguishes exact algebraic closure from stochastic measurement restrictions and from the econometric question of long-run equilibrium. Project diagnostics remain provisional: cointegration is specification-sensitive and robust panel-wide cointegration has not been established. The paper ends with ''The End''"),
("1. Introduction","Cross-country panels combine heterogeneous national structures, common shocks, measurement differences, and incomplete observations. CQS provides a graph-based representation of relative quantities and cycle restrictions. Empirical content requires independent measurements and a falsifiable stochastic model; a quotient identity alone is not evidence of economic behaviour or causality."),
("2. Mathematical foundations","For a directed graph with vertex log-level vector z and incidence matrix B, log edge quotients satisfy r=Bz. If C is a cycle matrix, CB=0 and therefore Cr=0. With noisy observations r~=Bz+u, cycle residuals are s=Cr~=Cu. If edge-error covariance is Sigma, then Var(s)=C Sigma C-transpose. A covariance-aware statistic is Q=s-transpose (C Sigma C-transpose)^+ s. Its reference distribution depends on the specified error model and regularity conditions. For positive levels x_i on a closed cycle, q_i=x_i/x_(i+1) telescopes and product(q_i)=1; this is an algebraic identity."),
("3. Seven-variable framework","The variables are population, land area, population density (population divided by land area), Gini index, real GDP per capita in constant 2015 US dollars, total real GDP in constant 2015 US dollars, and general government final consumption expenditure as a percentage of GDP. The last indicator is not total government expenditure. There are six observed source indicators and one derived variable."),
("4. Sample and data","The fixed sample comprises 60 economies embedded in the script. World Bank indicators are SP.POP.TOTL, AG.LND.TOTL.K2, SI.POV.GINI, NY.GDP.PCAP.KD, NY.GDP.MKTP.KD, and NE.CON.GOVT.ZS. Raw long-form data, a country-year panel, and coverage diagnostics are saved. Missing Gini values are not interpolated. API revisions can change future snapshots."),
("5. Statistical and econometric design","The proposed sequence is coverage audit, descriptive statistics, cross-sectional dependence diagnostics, panel unit-root tests, structural-break analysis, long-run relationship tests, and error-correction modelling. Common shocks can induce cross-sectional dependence; deterministic terms, lag structures, bootstrap resampling units, and finite-replication resolution must be reported."),
("6. Long-run relationships and error correction","The provisional candidate pair is log real GDP per capita and general government final-consumption share. Earlier Engle-Granger results were weak and specification-sensitive; break tests found some unit-specific evidence; country-level CCE-ECM adjustment estimates do not establish panel cointegration. A CCE-augmented ECM group bootstrap did not reject. A four-statistic Westerlund-style Python implementation produced one isolated group-mean Gt rejection in the government-share-adjustment direction (bootstrap p=.005, BH q=.040); the other seven reported tests did not reject after adjustment. This isolated result is insufficient evidence of a stable panel-wide long-run relation."),
("7. Numerical validation","The project-specific four-statistic implementation is inspired by Westerlund (2007), not claimed to be bit-for-bit equivalent to a canonical reference implementation. Its synchronized block bootstrap is project-specific. Preliminary Monte Carlo experiments used 99 replications per calibration, validation, and alternative cell; selected null rejection rates exceeded nominal size. Equation-level verification and at least 399 replications per cell are required before confirmatory interpretation."),
("8. Coverage audit","Coverage is computed from the downloaded snapshot below. The table reports non-missing observations and does not impute missing values."),
("9. Limitations and interpretation","Population density is mechanically derived. GDP per capita multiplied by population is a consistency diagnostic, not an exact independent identity with total GDP. Gini coverage is sparse and survey-method dependent. General government final consumption is narrower than total public expenditure. Cross-sectional dependence, structural breaks, heterogeneous slopes, short time dimension, and data revisions limit inference. Exact quotient closure does not establish causation, convergence, or cointegration."),
("10. Reproducibility","Run python -m pip install pandas requests reportlab followed by python scripts/generate_empirical_paper.py --start YEAR --end YEAR. The script downloads the six World Bank series, constructs the derived variable, writes three CSV audit/data files under data/processed/, and generates this PDF in the repository root. The workflow executes the same script. No R runtime or package is required.")
]
    for h,b in sections:
        story.extend([Paragraph(h,st["Heading1"]),P(b)])
        if h.startswith("8."):
            rows=[["Variable","Non-missing","Total","Coverage (%)"]]
            for _,r in cov.iterrows(): rows.append([r.variable,str(int(r.nonmissing)),str(int(r.observations)),f"{r.coverage_pct:.1f}"])
            t=Table(rows,repeatRows=1,colWidths=[78*mm,27*mm,22*mm,27*mm])
            t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("GRID",(0,0),(-1,-1),.4,colors.grey),("FONTSIZE",(0,0),(-1,-1),8),("ALIGN",(1,1),(-1,-1),"RIGHT")]))
            story.extend([t,Spacer(1,8)])
    story.extend([Paragraph("References",st["Heading1"]),
      P("Engle, R. F., and Granger, C. W. J. (1987). Co-integration and error correction: Representation, estimation, and testing. Econometrica, 55(2), 251-276."),
      P("Pesaran, M. H. (2006). Estimation and inference in large heterogeneous panels with a multifactor error structure. Econometrica, 74(4), 967-1012."),
      P("Westerlund, J. (2007). Testing for error correction in panel data. Oxford Bulletin of Economics and Statistics, 69(6), 709-748."),
      P("World Bank. World Development Indicators. https://databank.worldbank.org/source/world-development-indicators")])
    story.extend([Paragraph("The End",st["Heading1"])])
    SimpleDocTemplate(str(path),pagesize=A4,rightMargin=20*mm,leftMargin=20*mm,
      topMargin=18*mm,bottomMargin=18*mm,title=TITLE,author=AUTHORS).build(story)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--start",type=int,default=2000); a.add_argument("--end",type=int,default=2025)
    a.add_argument("--output",default=PDF); a.add_argument("--output-dir",default="data/processed")
    x=a.parse_args()
    if x.start>x.end: a.error("--start must be <= --end")
    out=Path(x.output_dir); out.mkdir(parents=True,exist_ok=True)
    p,c=acquire(x.start,x.end,out); render(p,c,x.start,x.end,Path(x.output))
    print(f"Generated {x.output}; rows={len(p)}; countries={p.iso3.nunique()}")
if __name__=="__main__": main()
