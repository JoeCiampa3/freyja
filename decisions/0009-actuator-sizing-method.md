---
id: adr-0009
status: accepted
date: 2026-11-12
links: [adr-0008, adr-0019, adr-0036, adr-0037]
---
## Context

This record closes rm.v1-actuator-sizing-method. It is the actuator counterpart of 0019 and settles six things: what a demand is when it reaches an actuator, where the statistic is taken, which checks an actuator must pass and with what factors, how duty enters, what a catalog entry must cite, and how a requirement record becomes an actuator spec. It selects no actuator and sets no demand.

State of play.
- 0019 D1(a) sizes every structure to T_pk,j "as 0009 defines it" and credits no firmware or controller limit (0036). So this record must define T_pk as a hardware number, separate from whatever torque the sizing checks allow.
- 0008 D7 hands over the elbow rows and leaves four things here (D9): the safety factor, the swing statistic, duty cycle and thermal sizing.
- rm.v1-map-method (0035) is blocked by this record, so the contract between the map and the sizing method is fixed here and the transform itself there.
- `sim/runs/ENVELOPE.md` says it is not a sizing basis. `sim/benchmarks/gait_extract.json` holds per-hinge statistics of stride peaks (95th percentile and maximum of torque, speed, positive power and regeneration). It holds no time series and no RMS.
- `catalog/` has no actuator entry.
- The approach on the node stands: lock a trusted demand, then put the factor on top, and never lower the factor to cover a doubtful number. From the Oct 2026 arm discussion: headroom is checked as a trajectory on the torque-speed curve, not as two independent peaks.

Tags are as in 0019: [design], [source: ...], [source needed], [derived].

## Decision

**D1 Demand.** A joint's demand is a set of load cases. Each case is a set of trials, and a trial is a time series of angle, speed and torque on the model's hinge axes, with every hinge of the joint sampled at the same instants. A static case is a trial of one sample at zero speed. A closed-form profile (0008 D3's minimum-jerk rows) is one trial.

Which cases a joint has, from what source, and which rows are admissible are for its load-basis record (0008 for the elbow), not for this one. The load-basis record also states, per case:
- its recurrence class, recurring or rare (D5c);
- whether its duration is bounded, and if so the duration and the rest that follows (D5a);
- its share of powered time, where it has one (D5b).

A demand carries no factor, no margin and no allowance. A case that is a single literature peak with no speed history enters as one sample and can close only the envelope, peak and tail rows of D4. The thermal and life rows need trajectories. A case with one trial has no distribution: its 95th percentile and maximum are that trial's value, and its rows carry the case's own status (0008's swing rows stay provisional). Rows labelled not for sizing never enter (0019 D1b).

**D2 The map contract.** This is what 0035 must deliver. The transform is 0035's.

(a) The map takes a case's trials on the hinge axes and returns, per actuator, trials in that actuator's own coordinates: torque and speed at the output its catalog ratings refer to, sample by sample. A coupled actuator's sample is computed from the simultaneous samples of every hinge it serves.

(b) Every statistic in D3 is taken after the map. A statistic of hinge-axis torque is never mapped. For a coupled or pose-dependent transmission the peak of a combination is not the combination of the peaks, and for a directly driven hinge the two orders agree, so one rule serves both.

(c) Transmission between the actuator's output and the hinge (cable, linkage, screw and crank) belongs to the map, with its ratio at each sample's pose and its efficiency applied in the direction of power flow: demand torque is divided by η when the actuator drives the joint and multiplied by η when the joint drives the actuator [design: the rule; each η is cited or tagged in the map's file].

(d) A built-up actuator (a frameless motor with its own screw or gear stage) is a chain of rated elements. The map carries the trials to each element's coordinates, and each element with a catalog entry gets its own rows in D4.

(e) The map's output is generated and reproducible from a clean clone (CONVENTIONS section 1). It must let the envelope row of D4 be evaluated against any candidate, so statistics alone are not enough: it keeps the (torque, speed) samples or a set that provably bounds them. The format and location are 0035's.

**D3 Statistics.** Per actuator and per case, from the mapped trials. Before any statistic, the candidate's own inertia torque (output-referred rotor and gear inertia times the output acceleration of each sample) and its cited friction are added to each sample, unless the simulation's model already carries them for that joint [derived: the actuator accelerates itself; source: the entry's inertia, D6]. The statistics are therefore per candidate.

(a) *Envelope set.* Every signed (torque, speed) sample of every trial, all four quadrants.

(b) *Peak.* Each trial's maximum absolute torque. The statistic is the 95th percentile across trials, with the maximum beside it [design]. A trial is the load-basis record's unit (a subject-stride in the gait data).

(c) *RMS.* The root mean square of torque over all samples of all trials of the case, time-weighted. It is pooled, not a percentile, because heat integrates over many trials [design].

(d) *Cubic mean.* T_cm = (Σ |T|^p |ω| Δt / Σ |ω| Δt)^(1/p) over all samples of the case, with p = 3 unless the entry cites its own exponent [source needed: the catalog's life method, cited in the first entry that has one]. Across cases the same sum runs over every case, each weighted by its output revolutions in the working life (D5b). Samples at zero speed add no revolutions and do not enter.

(e) *Dissipation.* P = T_rms² / K_m², with K_m the motor constant referred to the output (D6), per continuous case. Reported, never checked (D7).

**D4 Checks, classes and factors.** An actuator passes when every row below holds for every case. Rows are checked on their own and never netted.

| Check | Demand | Capability (D6) | Balance | Task |
|---|---|---|---|---|
| Envelope | every sample of D3(a), recurring cases | torque-speed boundary at the minimum bus voltage, torque no higher than T_rep | 1.5 | 1.25 |
| Recurring peak | 95th percentile of D3(b), recurring cases | T_rep | 1.5 | 1.25 |
| Tail | maximum of D3(b) for recurring cases; every sample of rare cases | T_mom, and the boundary with torque up to T_mom | 1.0 | 1.0 |
| Thermal | D3(c), each continuous case | T_cont | 1.25 | 1.25 |
| Life | D3(d) over the working life | T_life | 1.0 | 1.0 |

All factors are [design].

*How a factor is applied.* The factor n multiplies demand torque: a sample (T, ω) passes the envelope row when (n T, ω) lies inside the boundary. Speed takes no factor; its margin is the minimum bus voltage [design]. Each row reports its utilization u = n × demand / capability and passes at u ≤ 1. A row that misses is a finding with its number. The factor is not adjusted, for a doubtful demand or for a candidate that almost fits.

*The boundary.* The minimum bus voltage is the lowest the bus reaches under load, from 0028 [source: 0028, not yet written]. Until 0028 exists the entry's rated voltage is used and the row is provisional. In the braking quadrants, where the entry cites no curve, the limit is the entry's current-limited torque up to its maximum speed [design].

*Classes.* A joint is **balance** if it lies on the chain between a foot and the thorax, and **task** otherwise [design]. Balance: ankle, knee, hip (all three axes), lumbosacral, and the thoracolumbar and toe joints if they are ever actuated. Task: shoulder, elbow, wrist, and the cervicothoracic joint if actuated. An actuator takes the class of the joint it acts across, and the higher class if it acts across two. The class is a property of the joint, never of the actuator or the candidate.

*What the factors are for.* The balance factor on the envelope and peak rows is control reserve. Every demand available today is the feed-forward torque of a nominal motion, and a controller that rejects disturbances needs authority above it. The task factor is the smaller reserve of a joint whose saturation costs a task and not a fall. The thermal factor covers duty the cases do not describe; 1.25 on RMS torque is 1.56 on heat. The tail row has factor 1.0 so that the worst observed trial is deliverable, which keeps the tail from consuming the peak factor unseen. The life row has factor 1.0 because 0019's working life is already the margin. No factor covers confidence in the demand, in either direction; that is the load-basis record's business.

**D5 Duty.**

(a) *Thermal.* Every case is continuous: it is assumed to last longer than any thermal time constant of the actuator. A case is checked as intermittent only when its load-basis record gives a bounded duration and rest and the catalog entry cites a thermal model (a time constant or an overload curve) to check it against [design]. The governing case is the largest RMS among the continuous cases. Cases are not averaged together. T_cont is taken at the thermal conditions its entry cites.

(b) *Life.* The working life is 0019 D2's (29,200 powered hours, half of it walking), read by reference and not restated in any spec. Walking takes its share from 0019. Any other case's share of powered time is stated in its load-basis record [design]. The remainder is standing.

(c) *Recurrence.* A case is **rare** if it is expected no more than 10^4 times in the working life [design; source needed: the count behind a catalog's momentary rating] and **recurring** otherwise. A stride peak occurs 5e7 times (0019 D2) and is recurring. Stumble recovery and a hard-stop strike are rare. A rare case enters only the tail row.

**D6 The catalog entry.** An actuator entry in `catalog/` cites each of the following (datasheet and page, vendor correspondence, or a bench record), or tags it.

- **T_pk**: the largest output torque the hardware can deliver, the greater of the datasheet peak and the stall torque at the driver's hardware current limit. This is the T_pk of 0019 D1(a). No firmware or software setting lowers it.
- **T_mom**: the momentary rating, the largest torque allowed for rare events. T_mom ≤ T_pk.
- **T_rep**: the repeated-peak rating, the torque allowed at every cycle for the working life.
- **T_cont**: the continuous torque, with the ambient temperature and mounting it assumes.
- **T_life**: from the entry's life rating (rated torque, rated speed, rated life, exponent), the torque at which that rule gives the working life's output revolutions.
- The torque-speed boundary at stated voltages, the current limit, the maximum speed.
- K_m at the output, or the torque constant, phase resistance at a stated temperature, ratio and efficiency it derives from.
- Ratio, efficiency in each direction, output-referred inertia, friction, backlash, torsional stiffness, mass, and a thermal time constant where one exists. rm.v1-actuator-models reads these.

*Where the datasheet is silent* [design]:
- No T_rep: T_rep = T_cont. It is the only torque the vendor states the unit carries without limit, and no fraction of T_pk has a source. It is replaced by a vendor statement, a gear rating computed by a script in `analysis/` from measured tooth data, or an endurance record from rm.v1-actuator-bench.
- No T_mom: T_mom is the datasheet peak.
- No life rating: the life row is reported as unrated and does not close. The selection record says that it rests on the T_rep row.
- No boundary: the envelope row does not close. A boundary may be built from cited points by a script in `analysis/`.
- No thermal model: every case is continuous (D5a).

A bench record replaces a datasheet value in either direction, by an edit to the entry that cites the record.

**D7 Dissipation and the enclosure.** The generated spec reports D3(e) per actuator for each continuous case, and the sum per housing segment. It is copper loss only, so it is a lower bound on heat until iron and friction losses are cited. No limit is set in v1. The thermal limit of a segment under foam and skin belongs to the version that fits them, and v1 claims nothing about it. Every selection record states the dissipation of each candidate it compares, because the same joint torque costs different heat in different actuators, and 0029 reads the same numbers.

**D8 From requirement to spec.** A requirement record states a demand and carries no factor (as 0019 D5). An actuator's spec is generated, not authored: one row per actuator, case and check, each field resolved by address.
- The demand statistic, from the map's output (0035).
- The class, from the joint the part acts across.
- The factor, from the factor table.
- The capability, from the catalog entry.
- The required capability (factor times demand) and the utilization, computed.

The **factor table** is one authored file holding D4's factors and the class of each `jnt.` id. This record decides the values. The table is their machine-readable home, and a table value that differs from an accepted record is a finding. Its location and schema are settled with the first generated spec, the elbow's (rm.v1-elbow-actuator-selected), with the CONVENTIONS edit in the same commit. This record adds no record kind.

A candidate is admissible when every row that can close has u ≤ 1. Choosing among admissible candidates (mass, volume, dissipation, backlash, reflected inertia, and the structural cost of T_pk under 0019) is for the selection record, which states the selected unit's T_pk.

## Consequences

- 0019 D1(a) now has its T_pk. A software torque cap is an operating choice and changes no row here or there.
- Actuator margin is paid twice. A candidate must offer at least n times the demand, its T_pk is at least that, and 0019 puts a factor of 2 on yield at T_pk. Oversizing an actuator is a structural cost, and the selection record carries it.
- With T_rep defaulting to T_cont, an actuator with no repeated-peak rating is sized on its continuous torque for gait peaks. This is the heaviest [design] rule in the record and the first thing vendor data or the bench should replace.
- The gait extract cannot feed this method as it stands: it has no simultaneous hinge time series and no RMS. The map leaves need the pipeline to emit trials, which is a brief for Code alongside 0035.
- `sim/runs/ENVELOPE.md` stays not a sizing basis. This record changes no demand.
- The elbow is the first consumer. From 0008 D7, at the hinge and before its map: task class; the static design-payload hold is continuous, so the thermal row asks 1.25 × 5.00 = 6.25 N·m of T_cont; row S3 asks 1.25 × 6.3 = 7.9 N·m of T_rep along its trajectory to 2.95 rad/s, provisional as S3 is [derived]. The swing rows are single trials and have no statistic.
- The envelope row is provisional for every joint until 0028 gives the minimum bus voltage.
- 0029 reads mechanical power, regeneration and D7's dissipation per actuator from the generated specs.
- Open: the shares of powered time and the counts of the non-walking cases; the source of the exponent p; a source for the 10^4 count; iron and friction losses; whether catalog life ratings (a 90% reliability figure by convention) should be adjusted as 0019 D2 adjusted fatigue; whether 0019's factors join the factor table.
- Revisit trigger for the balance factor: the first walking controller. The ratio of its closed-loop torque under disturbance to the feed-forward torque of the same motion is the measured control reserve, and it replaces 1.5 by a superseding record.
- Changing a factor, a class rule or a default of D6 means superseding this record.

## Rejected options, and why each one died

**D1 to D3.**
- *Peak torque against peak torque and peak speed against peak speed.* The two peaks do not coincide, and gravity torque acts at rest. Two independent peaks size for a point the joint never visits and miss the points it does.
- *Mapping the hinge statistics.* The 95th percentile of a coupled actuator's torque is not a function of the hinge percentiles.
- *The maximum as the peak statistic.* It grows with the number of trials and follows single outliers: at 1.4 m/s the left hip's flexion row is 74.3 N·m at the 95th percentile, 138.2 at the maximum and 223.0 unfiltered. It is kept at factor 1.0 in the tail row.
- *A percentile of per-trial RMS.* Heat integrates across trials, so the pooled value is the physical one.
- *Leaving the candidate's own inertia out.* A high-ratio candidate would be credited with torque it spends accelerating itself.

**D4.**
- *One factor for every check.* Each row covers a different unknown, and a single factor on RMS torque squares into heat.
- *A factor authored per actuator.* It is the number that gets changed when a candidate does not fit.
- *A factor that reflects confidence in the demand.* Against the approach on the node, in both directions.
- *The stride peak against the datasheet peak.* A load that recurs 5e7 times is a fatigue load, and a momentary rating says nothing about it.
- *A factor on speed as well.* The reserve a controller needs is torque. Speed margin comes from the bus voltage.
- *A factor on the life row.* The working life is already the margin, and a second one stacks.

**D5.**
- *The life-average duty for the thermal row.* Half of powered time walking does not stop an hour of continuous walking.
- *Intermittent ratings by default.* Thermal time constants are unknown until an actuator is benched.

**D6 and D7.**
- *T_pk as the software-capped torque.* Behaviour credit (0036, 0019 D1).
- *A fraction of T_pk as the default T_rep.* No fraction has a source.
- *A skin or enclosure thermal limit in v1.* The skin does not exist, and its limit would be invented. The dissipation it will have to pass is recorded instead.
- *Dropping dissipation because the limit is deferred.* It differs severalfold between candidates at the same joint torque, and it is the one thermal number that depends on the actuator and the demand alone.

**D8.**
- *The factor in the catalog entry.* One product serves joints of different classes.
- *The factor typed into the part record.* A hand-typed copy (CONVENTIONS section 1).
- *The class on the thread's joint record.* It needs a schema change for one field. The factor table keys the class by `jnt.` id.
- *A new spec record kind.* As 0019 D5.
