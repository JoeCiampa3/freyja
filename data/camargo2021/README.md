# Camargo et al. 2021 dataset: audit (Stage 2 T0)

Everything here was read from the files, not assumed. Raw archives live in `data/camargo2021/raw/` (gitignored; override with
`$CAMARGO_RAW_DIR` or a `camargo_raw_dir` key in `sim/local_config.json`, which the code only reads). Attribution: `ATTRIBUTION.md`.
Ingestion: `analysis/ingest_camargo.py`, spec `ingest_spec.yaml`, output `manifest.json` (tracked) and `processed/` (gitignored).

## Layout
- Delivered as one zip per subject (`AB06.zip` ... `AB23.zip`, 1.0 to 1.5 GB each, 17 subjects), not the nine-subject archive the brief
  named. Inside: `osimxml/` (OpenSim model `<subject>.osim`, IK and ID setup files) and `<date>/<mode>/<sensor>/<mode>_NN_01.mat`.
  Modes present: treadmill, levelground, ramp, stair, static. Sensors: conditions, emg, fp, gcLeft, gcRight, gon, id, ik, ik_offset,
  imu, jp, markers.
- `scripts.zip` is 42 MB uncompressed (the brief expected 204 MB): MATLAB code only (EpicToolbox, MoCapTools, BTK `.mexw64`
  binaries, a 32 MB `.trigno` device file). Nothing in it is data.
- Format: MATLAB v5 files holding one `table` (MCOS object), not v7.3, so `h5py` is not needed. scipy cannot decode the table
  class; `read_table` parses its subsystem with scipy's own stream reader (tested).
- Treadmill: 7 to 9 trials per subject. A trial is a speed schedule (for AB06 trial 1: 0.5, 1.3, 1.7, 0.9 m/s ...), 28 speeds in
  0.05 m/s steps over the trials; each trial's plateaus last about 32 s. 1.4 and 1.6 m/s are each one plateau per subject.

## Channels, units, rates
| Sensor | Rate | Content |
|---|---|---|
| ik | 200 Hz | 24 OpenSim coordinates, degrees (pelvis translation m): pelvis_tilt/list/rotation/tx/ty/tz, hip_flexion/adduction/rotation, knee_angle, ankle_angle, subtalar_angle, mtp_angle (right `_r`, left `_l`), lumbar_extension/bending/rotation (all zero) |
| id | 200 Hz | the same coordinates as generalized forces: N m for angles (NOT normalised; `STRIDES.m` divides by mass when it plots), N for pelvis translation. Filtered at 6 Hz in `RUN_OSIM.m`. Pelvis rows are OpenSim's residuals (peak ~70 to 200 N) |
| fp | 1 kHz | per plate `Treadmill_R` / `Treadmill_L`: force `vx vy vz` (N), CoP `px py pz` (m, `py` = 0), `moment_x/y/z` (N m). Forces are exactly 0 in swing. The moment channels do not satisfy M = p x F in z; they are not used |
| conditions | 1 kHz | belt `Speed` (m/s), changes in 1 mm/s steps during accelerations |
| gcLeft/gcRight | 200 Hz | gait phase ramps `HeelStrike`, `ToeOff` (0 to 100); not used, events come from the force |
| jp | 200 Hz | joint power, not used (computed here) |
Markers are in mm. Subject table `SubjectInfo.mat` (22 subjects): age, sex, height (m), weight (kg). Peak vertical force of 1.13
to 1.45 body weights per subject confirms kg.

## Frames and signs (evidence in `sim/scenarios/gait/camargo_mapping.yaml`)
- Lab frame (= OpenSim ground): x subject's right, y up, z backward. Heel and toe markers give the foot pointing along -z;
  ASIS markers give right = +x; `pelvis_rotation` sits near 90 degrees for that reason.
- Joint angles follow gait2392 conventions: hip flexion +, adduction +, rotation + (internal); **knee_angle is negative in flexion**;
  ankle_angle + dorsiflexion. Subtalar and hip rotation signs are not testable with sagittal features (unverified).
- The dataset has no CoM or ground-reaction data in a body-fixed frame; everything is in the lab frame.

## Pelvis angle meanings (do not trust the coordinate names)
OpenSim's `pelvis_tilt`, `pelvis_list` and `pelvis_rotation` are rotations about ground z, x and y in the order Rz Rx Ry. The lab z axis
points along the walking direction (backward), so `pelvis_tilt` is the pelvis ROLL (obliquity), `pelvis_list` is its sagittal PITCH
(a rotation about the subject's right; anterior pitch is minus `pelvis_list`) and `pelvis_rotation` is YAW, about 90 degrees. The
manifest reports each subject's static and walking means for roll and pitch separately (`static_pelvis_roll_deg`,
`static_pelvis_pitch_deg`, `walking_pelvis_roll_deg`, `walking_pelvis_pitch_deg` per speed). The model's hip centres in the pelvis
frame (`hip_in_pelvis_os_m`) come from `osimxml/<subject>.osim`.

## Subjects used and speeds
17 subjects, AB06 to AB21 and AB23, 469 strides at 1.4 m/s and 519 at 1.6 m/s after the acceptance tests in `ingest_spec.yaml`
(zero rejections in this run; the settle time and 10 s plateau minimum remove the irregular steps at the start of a plateau).
Subject mass 52 to 96 kg is for the dataset's own subjects only; Freyja's mass is separate.

## Third-party content
`scripts.zip` carries MIT-licensed code (EpicToolbox, MoCapTools), Apache-2 and MIT libraries (YAMLMatlab, snakeyaml, minf) and
BTK binaries. None is used or redistributed here. The README names no third-party data.

## Licence
CC BY 4.0 (Part 2's Mendeley page, checked 2026-10-11; Part 1 per Joe; Part 3 unchecked and not used yet). CC BY 4.0 permits
derived data with attribution; nothing prohibits it. The README itself states no licence text; the Mendeley page does.

## Known quirks
- Right-plate contacts include short cross-over steps by the left foot (a 0.38 s blip in AB06 trial 3); `min_contact_s` removes them.
- Ankle angle at toe-off sits above 0 for two subject-speed groups (AB13 at 1.4, AB15): a subject offset in the IK zero, not a sign
  error (their toe-off angle is still 16 to 23 degrees below the stance peak). The feature check is applied to the pooled sample.
