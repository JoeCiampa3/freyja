---
origin: me
---

## What it is

Errors were noticed in the BSIP table of the anthropometric reference sheet. They were corredted but their presence warrants a full manual sweep over each row of the table to verify they match the papers drawn from 

## Findings

Every row was checked against the corresponding paper. Dumas 2007 page 548 is the principle source (pelvis, thigh, shank, foot, upper arm, forearm, hand), the corrigendum (availavle on ScienceDirect) for head and neck, Dumas 2015 page 116 for thorax and abdomen. Our radii of gyration entries are out of order with the paper's (ours is r_yz before r_xz). Every number was verified by manually matching it to the corresponding entry in Dumas. There were no numerical discrepancies identified.

Two non-numerical problems were found. 

(1) The upper arm, forearm, hand, and foot segments do not have a scale applied. They are the unaltered Dumas lengths. Our model is a 170cm woman with the arm and foot lengths of a 162cm woman. The currently proposed fix: apply the scale to each of the remaining segments. 

(2) The scale factor is computed assuming every segment is lined up with the segment length along the vertical. In reality, human posture is quite difference, especially for the pelvis. The posture needs to be decided upon so the scale factor matches what it is intended for. 

