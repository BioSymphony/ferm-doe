# Scale-Bridge Entry Conditions: Flask Screening to STR Transferability

**Template version:** 1.0
**Purpose:** Force every flask-based screening campaign to prove its aeration regime is non-limiting BEFORE claiming the resulting recipe rankings are transferable to stirred-tank reactor (STR) scale. A campaign that cannot fill this template must surface its flask data as O2-regime artifacts, not media-recipe rankings.

## Why this template exists

Shake-flask screening campaigns can ship media-ranking claims that are
structurally oxygen-limited rather than media-driven. An unbaffled 250 mL
flask at 200 rpm with a 2.5 cm orbital throw has kLa about 15 to 30 per hour
and OTR_max about 5 to 10 mmol O2/L/h (Maier-Buchs correlation). E. coli
BL21 at mu about 0.3 per hour consumes O2 at about 4 mmol O2/g DCW/h
(Garcia-Ochoa and Gomez 2009 prior), so the flask oxygen-limits at DCW about
1.5 to 3 g/L (OD600 about 4 to 9), well before product titer signals can separate
media recipes. The flask ranking that comes out of such a campaign reflects
which recipes happen to slow growth enough to stay under the OTR ceiling,
not which recipes support best periplasmic-pathway expression. A 2 L STR
at kLa about 400 per hour will then rank-disagree with the flask data, and
the apparent "failure to translate" gets misdiagnosed as a media problem
when it is an aeration problem at the small scale. The mitigation, baffled
500 mL flask plus sulfite-method kLa calibration plus PreSens DO patch, is
formalized as a campaign risk register entry and codified here as a
pre-screen checklist.

## When to fill

Before any campaign declares that its flask-based recipe rankings are
transferable to STR scale. Before any media optimization claim is derived from
shake-flask data. This template must be completed and committed alongside the
handoff packet whenever a campaign's design tournament shipped a ranking
generated at the flask scale; the lab team should refuse to schedule STR runs
against an unfilled or `NOT TRANSFERABLE` packet.

## Conventions

- Fields marked `REQUIRED` fail the entry-condition check if blank or unmet.
- Fields marked `OPTIONAL` may be omitted but their absence should be deliberate.
- Placeholders use `{{double-braces}}`; replace inline.
- This is a DOE planning / entry-condition artifact, not a batch record. Do
  not add operator initials, lot tracking, IPC alert/action runtime, deviation
  logs, or 21 CFR 211.188 scaffolding. Those belong in the lab team's batch
  record built on top of this entry condition.

---

## Section 1: Campaign and biological system

| Field | Value |
|---|---|
| Campaign ID (REQUIRED) | {{campaign_id}} |
| Organism + strain (REQUIRED) | {{e.g., `E. coli BL21(DE3)` or `Pichia pastoris X-33`}} |
| Target product class (REQUIRED) | {{`extracellular` \| `periplasmic` \| `intracellular` \| `secreted`}} |
| Product expression pathway notes (OPTIONAL) | {{e.g., "periplasmic via pelB, Dsb-dependent disulfide formation"}} |
| Expected DCW range over run (REQUIRED) | {{low to high g/L over the run trajectory}} |
| Expected mu at peak growth (REQUIRED) | {{per hour, used to estimate OUR ceiling}} |
| qO2 prior used (REQUIRED) | {{mmol O2/g DCW/h, with citation; typical E. coli 10 to 15, Pichia 4 to 8, CHO 0.1 to 0.5}} |

---

## Section 2: Equipment and geometry

| Field | Value |
|---|---|
| Flask type (REQUIRED) | {{`round (unbaffled)` \| `baffled`; REQUIRED `baffled` for DCW targets > 5 g/L, or justify why round is acceptable for this product/DCW combination}} |
| Round-flask justification (REQUIRED if `round`) | {{free text, e.g., "DCW target <= 2 g/L throughout, growth phase is non-binding, expression is constitutive at low mu"}} |
| Nominal flask volume (REQUIRED) | {{mL}} |
| Working volume (REQUIRED) | {{mL; recommend <= 20% of nominal; flag if higher}} |
| Fill ratio (REQUIRED) | {{working/nominal; recommend <= 1:5}} |
| Shaker orbital throw (REQUIRED) | {{mm; typical 25 or 50}} |
| Shaker frequency (REQUIRED) | {{rpm}} |
| Plug type (REQUIRED) | {{`foam` \| `silicone` \| `membrane (AirOtop or equivalent)` \| `other`}} |
| Plug O2 permeability source (OPTIONAL) | {{vendor spec or citation if plug-limited gas exchange is a concern}} |
| Replicate flasks per condition (REQUIRED) | {{N}} |

### 2.1 kLa derivation source

| Field | Value |
|---|---|
| kLa source (REQUIRED) | {{`correlation only` \| `sulfite measurement` \| `OUR-based estimate` \| `gassing-out`}} |
| If `correlation only`: which correlation (REQUIRED) | {{`Maier-Buchs 2004` \| `Van't Riet 1979` \| `Buchs-Klockner 2000` \| other with citation}} |
| Correlation reference (REQUIRED if `correlation only`) | {{PMID/DOI}} |
| If measured: measurement protocol citation (REQUIRED if measured) | {{e.g., "sulfite oxidation per Linek-Vacek 1987"}} |
| Measurement date (REQUIRED if measured) | {{YYYY-MM-DD}} |
| Measurement operator (REQUIRED if measured) | {{name or role}} |

---

## Section 3: Mass transfer (OTR ceiling vs. demand)

| Field | Value | Pass/Fail |
|---|---|---|
| kLa target (REQUIRED) | {{per hour}} | REQUIRED >= 100 per hour for BL21 at mu >= 0.3, or justify lower |
| kLa actual (REQUIRED) | {{per hour; MEASURED VALUE, not correlation; if only correlation is available, state `correlation_only` and treat Section 6 as a FAIL on this check}} | Compare to target |
| Justification if kLa target < 100 per hour (REQUIRED if target lowered) | {{free text, e.g., "low-mu slow-growth screen, OUR ceiling not binding at DCW target"}} | n/a |
| OTR_max (REQUIRED) | {{mmol O2/L/h; derived: OTR_max = kLa_actual x (C* − C_min) x (0.21/22.4), where C* about 0.21 mmol O2/L at 30 C atm air, C_min set by DO_target}} | n/a |
| DCW at which OTR_max is reached (REQUIRED) | {{g/L; derived: DCW_OTR_max = OTR_max / (qO2 x mu), with qO2 from Section 1}} | n/a |
| DCW target for campaign (REQUIRED) | {{g/L; peak culture density expected at sampling/harvest}} | n/a |
| Headroom (REQUIRED) | {{DCW_target / DCW_OTR_max; derived}} | REQUIRED >= 1.5 for transferable rankings |

**Worked formula reference (Van't Riet, Maier-Buchs):**
`OTR_max [mmol O2/L/h] = kLa [per hour] x dC [mmol O2/L]` where
`dC = (C* − C_min) = (0.21 mmol/L) x (1 − DO_setpoint_fraction)` at 30 C, 1 atm air.
For a flask running open to atmosphere with DO_setpoint = 0.30, `dC about 0.147 mmol/L`.
`DCW_at_OTR_max [g/L] = OTR_max / (qO2 x mu_max)`. See
[`docs/SCALE_BRIDGE_METHODOLOGY.md`](../docs/SCALE_BRIDGE_METHODOLOGY.md) §2.1, §2.6, §10.

---

## Section 4: DO monitoring

| Field | Value | Pass/Fail |
|---|---|---|
| DO probe type (REQUIRED) | {{`PreSens dot (optical patch)` \| `inline polarographic` \| `inline optical (Hamilton VisiFerm)` \| `none`}} | REQUIRED non-`none` for TRANSFERABLE |
| DO calibration date (REQUIRED if probe present) | {{YYYY-MM-DD}} | n/a |
| DO calibration standard (REQUIRED if probe present) | {{`air-saturated 100%` \| `nitrogen-purged 0% + air-saturated 100% (2-point)` \| other}} | 2-point preferred |
| DO at peak growth (REQUIRED if probe present) | {{% saturation, lowest observed during high-OUR phase}} | REQUIRED >= 30% |
| DO-limited episodes during run (REQUIRED) | {{`Y` / `N` + duration in min if `Y`}} | `N` for full transferability; `Y` with `< 10% of run duration` is a CAVEAT |
| DO trace artifact path (OPTIONAL) | {{path to logged trace, e.g., `artifacts/<campaign>/do_trace.csv`}} | n/a |

If `DO probe type = none`, this section automatically FAILS; DO cannot be
asserted >= 30% without measurement. Section 6 verdict defaults to
`NOT TRANSFERABLE`.

---

## Section 5: Substrate and metabolite signals

| Field | Value | Pass/Fail |
|---|---|---|
| C-source feed strategy (REQUIRED) | {{`batch` \| `fed-batch (exponential)` \| `fed-batch (DO-stat)` \| `pulse`}} | n/a |
| Acetate accumulation observed peak (REQUIRED) | {{g/L peak; measured by HPLC, enzymatic kit, or note `not measured`}} | REQUIRED < 2 g/L for E. coli BL21 to claim non-overflow regime |
| If acetate measurement is `not measured`: justification (REQUIRED if not measured) | {{free text, e.g., "low-glucose batch (<= 5 g/L initial), C/N ratio engineered to suppress overflow, organic-acid HPLC not in inventory"}} | n/a |
| Residual carbon source at sampling (REQUIRED) | {{g/L at the sampling time used for ranking}} | n/a |
| Acetate + DO co-signal check (REQUIRED) | {{`pass` \| `fail`; FAIL if acetate > 2 g/L AND DO < 30%; this co-occurrence is a strong O2-limitation signature regardless of kLa correlation}} | n/a |

Note: acetate > 2 g/L combined with DO < 30% strongly indicates O2 limitation
for E. coli BL21 regardless of whether the kLa correlation suggests
adequate aeration. Either signal alone is a yellow flag; both together is red.

---

## Section 6: Transferability decision

| Check | Threshold | Pass/Fail |
|---|---|---|
| kLa actual >= 100 per hour (or justified lower) | Section 3 | {{P/F}} |
| DCW headroom >= 1.5 | Section 3 | {{P/F}} |
| DO probe present AND DO >= 30% at peak growth | Section 4 | {{P/F}} |
| Acetate < 2 g/L (or non-overflow regime justified) | Section 5 | {{P/F}} |

| Verdict | Condition | Action |
|---|---|---|
| **`TRANSFERABLE`** | ALL four checks pass | Rankings provisional pending STR confirmation; proceed to STR design with flask ranking as informative prior. Reviewer signoff required. |
| **`TRANSFERABLE_WITH_CAVEAT`** | Some checks pass; specific limited failure | Specify which check(s) failed in the caveat field below and explicitly state how that constrains the interpretation (e.g., "rankings valid for low-DCW recipes only; high-DCW candidates not transferable without re-screen"). Reviewer signoff required; lab_team_brief.md must surface the caveat. |
| **`NOT TRANSFERABLE`** | ANY check fails outright AND no caveat-narrowing is justified | Flask rankings reflect O2-limitation artifacts. They cannot be used to claim recipe ordering for STR scale. Required mitigation: measure kLa by sulfite method, fit PreSens DO patch, switch to baffled 500 mL + 5 cm throw, re-screen. Reviewer signoff still required to document the gating decision. |

| Field | Value |
|---|---|
| Final verdict (REQUIRED) | {{`TRANSFERABLE` \| `TRANSFERABLE_WITH_CAVEAT` \| `NOT TRANSFERABLE`}} |
| Caveat scope (REQUIRED if `TRANSFERABLE_WITH_CAVEAT`) | {{which check(s) failed, how that constrains the interpretation, and which subset of recipes / DCW range / induction regime is still transferable}} |
| Required re-screen actions (REQUIRED if `NOT TRANSFERABLE`) | {{ordered list; typically (1) sulfite kLa calibration, (2) PreSens DO patch fit, (3) baffled flask + 5 cm throw + <= 1:5 fill, (4) re-run priority candidates}} |
| Linked risk register entry (REQUIRED) | {{e.g., `examples/<campaign>/handoff-packet/risk_register.md :: R-{{CAMPAIGN}}-008`}} |

---

## Section 7: Signoff

| Field | Value |
|---|---|
| Operator name (REQUIRED) | {{name or role, the person who filled this template}} |
| Operator date (REQUIRED) | {{YYYY-MM-DD}} |
| Process engineer reviewer name (REQUIRED if verdict is `TRANSFERABLE` or `TRANSFERABLE_WITH_CAVEAT`) | {{name or role, independent of the operator; lab team owns reviewer assignment}} |
| Process engineer reviewer date (REQUIRED if verdict is `TRANSFERABLE` or `TRANSFERABLE_WITH_CAVEAT`) | {{YYYY-MM-DD}} |
| Commit SHA where this completed file is committed (REQUIRED) | {{git commit SHA; fill after the commit lands}} |

For `NOT TRANSFERABLE` verdicts, reviewer signoff is OPTIONAL; the operator's
decision to block STR transferability stands on its own, and the re-screen
loop will produce a new copy of this file once mitigations are in place.
