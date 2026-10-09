$$
\LARGE \textbf{Sprint I Memo}
$$

$$
\Large Build
$$
Sprint I and Ib focus on creating and evaluating the first iteration of the Freyja MuJoCo model. This model will eventually be used for everything from inverse kinematic driven actuator sizing to simulating fall impacts and designing and testing controllers.

The model contains sixteen rigid segments. Lengths and inertial data are sourced from the ground truth anthropometric reference document. All major joints have been built in with the exception of fingers and toes. Several joints have been simplied for the initial version (see deviations). Simple geometry such as capsules, spheres, and elipses are used for visual aid and will eventually be replaced by the segment meshes. 

To avoid manual transcription error, every physical value (eg segment masses, lengths, joint roms,...) in the MJC model is pulled directly from the ground truth Anthropometric Reference sheet and pushed to the model. The vehicle for this is the Python program pre_processor in scripts\ which is now complete. It was initially human written until it was tested and working for BSIP data, the remaining work was deligated to Claude Code to expand the functionality to include RoM and position data. In addition, it was further fleshed out with checks, failsafes, and quality of life upgrades (writing to a designated model file when broken, publishing param CSVs to an archive, etc), but the core loop was written and understood by the creator. At this point in time the program is fully functional and the only human interaction in the sheet to model pipeline is to run the pre_processor, which will eventually be automated away (currently low priority but will prevent accidental mismatches from forgetting to run pre_processor by updating the model live post sheet-update). models\freyja_template.xml is the template model that is maintained and iterated, when ready to use the models\scripts\freyja.xml the command line is used to run the pre_processor which pulls values from the sheet, checks and sanitizes them, reads from the template, and wherever a ${placeholder} is within the template it is replaced by the sheet value.

The pipeline from sheet to model begins with directly sourced biomechanics data in the relevant worksheet (eg BSIP worksheet uses Dumas), ISB coordinates (x anterior z to right, y superior) are used throughout. MuJoCo uses a different coordinate system, which requires the transform (x, y, z) (ISB) -> (x', y', z') = (x, -z, y) (MJC). For CoM this means undergoing the transformation

$$
\begin{bmatrix}
CoM\_x' \\
CoM\_y' \\
CoM\_z'
\end{bmatrix}

=

\begin{bmatrix}
1 & 0 & 0 \\
0 & 0 & 1 \\
0 & -1 & 0
\end{bmatrix}

\cdot

\begin{bmatrix}
CoM\_x \\
CoM\_y \\
CoM\_z
\end{bmatrix}
$$

And MuJoCo inertial parameters are computed from their ISB counterparts with the transformation

$$
\begin{bmatrix}
Ixx' & Ixy' & Ixz' \\
Ixy' & Iyy' & Iyz' \\
Ixz' & Iyz' & Izz'
\end{bmatrix}

=

\begin{bmatrix}
1 & 0 & 0 \\
0 & 0 & -1 \\
0 & 1 & 0
\end{bmatrix}

\cdot

\begin{bmatrix}
Ixx & Ixy & Ixz \\
Ixy & Iyy & Iyz \\
Ixz & Iyz & Izz
\end{bmatrix}

\cdot

\begin{bmatrix}
1 & 0 & 0 \\
0 & 0 & 1 \\
0 & -1 & 0
\end{bmatrix}
$$

Or


$$
I' = RIR^T = 

\begin{bmatrix}
Ixx & -Ixz & Ixy \\
-Ixz & Izz & -Iyz \\
Ixy & -Iyz & Iyy
\end{bmatrix}
$$

These transformations are applied within the worksheet itself, all transformed data is put into MuJoCo specific worksheets to be pulled by the pre_processor.  The MuJoCo sheet also alters the order of inertia entries to Ixx Iyy Izz Ixy Ixz Iyz to match the order MuJoCo's <inertial> entity expects. After updating any value within the worksheet, the pre_processor is run and it pulls all relevant data from the MJC worksheet tables, mirrors bilateral segments via the transformation

$$
\begin{bmatrix}
mirror\_pos\_x \\
mirror\_pos\_y \\
mirror\_pos\_z
\end{bmatrix}

=

\begin{bmatrix}
1 & 0 & 0 \\
0 & -1 & 0 \\
0 & 0 & 1
\end{bmatrix}

\cdot

\begin{bmatrix}
pos\_x \\
pos\_y \\
pos\_z
\end{bmatrix}
\newline
(MuJoCo->MuJoCo \space Coordinates)
$$

then reads the freyja_template.xml model and writes it to freyja.xml. As it does so every ${placeholder} written into the template is replaced by the corresponding value pulled from the worksheet.


The current state of the model is simple but complete, with a robust pipeline from the reference sheet to the model that makes basic iteration trivial.
$$
\Large Assumptions
$$

We are initially using a "ramrod" posture in which all body segment lengths (with the exception of the pelvis) are strictly vertical. In the future an attempt will be made to model the joint-to-joint connecting segments more accurately (especially for spinal joints). perhaps by using the makehuman mesh as an approximate neutral position and estimating joint posistions from it.  

Friction is initially hardcoded and uses ballpark values which will be tuned as the project progresses and material is selected for the feet. Condim is initially set to 3 and will eventuall be set to 4 or 6 to model rotation of the foot against the floor. 

The shoulder architecture has not been started on, as a placeholder it is designed here as a 3dof serial gimbal like the hip, with the order of joints being FE->AA->IER. A comment has been left in the template to ensure this is eventually updated with the chosen configuration.
$$
\Large Validations
$$
Validations this sprint lived in testing the pre_processor and the physical properties of the model. 

After returning to Dumas 2007, the spreadsheet mass closes to within 0.1% (64.935kg compared to target 65kg, discrepancy explained by rounding in Dumas' published segment mass fractions). The pre_processor contains a built in mass check every time it is run, and an independent python file importing the MJC model and evaluating the whole-body mass both agree on 64.935kg, exactly matching the sheets mass. We have concluded there is no perceptible mass loss through the transcription pipeline. 

To validate our model and its underlying data, we used scripts\mass_checks.py to compute not only mass but whole body CoM. To compare vertical whole body CoM to adult female data we are using the reaction board study by Virmavirta and Isolehto. Whole body CoM is reported as a percentage of total stature. Virmavirta and Isolehto report a range of 55.88% +/- 0.52%. Our model's CoM is calculated at 9.34912976e^-01 meters , as a percentage of stature it is approximately 55.26%, about 0.1% outside the study's range. The discrepancy is likely explained by using ANSUR II data for floor to AJC and Dumas for every other quantity, effectively creating inter-individual variation by using numbers from two studies. Furthermore, the pose for Dumas' CoM data and Virmavirta and Isolehto's subjects cannot be independently cross checked. This check is not a rigourous or precise validation but aims to spot any major errors. We have concluded the discrepancy is not statistically significant and will proceed with the current data.

The lateral CoM from our model was calculated to be -1.63073889e-04 meters or about -0.63mm. A value of 0mm would indicate a perfectly symmetric specimen, but humans are assymetric by nature. Dumas' data shows that the segments lateral CoM values are low but non-zero. This check is also not a fine-grained precision validation but rather a coarse check to ensure the model has been built correctly. Several mm would be a reason for concern, -0.16mm is low enough to be insignificant.

$$
\Large Deviations
$$

FIXME: explain joint simplifications for knee, ankle, wrist, spine, shoulders, etc.
Freyja's final form will include dextrous hands, potentially actuated toes, and a complex spine that is initially aimed at continuum architecture to better realize the goal of making her capable of the full human RoM. The design plans to build out the full working robot as a complete platform before iterating on each part to ensure progress is not bottlenecked. The main project goals are to build and test the pelvis and legs, building a walking prototype with a simplified upper body that will gradually be revised to fit the final vision. To reflect this, the v1 model leaves the hands and feet as one body without taking fingers or toes into account, to be added onto later if and when the current simplified architecture is no longer a sufficient description. The spine is modeled as three bodies: pelvis, abdomen, and thorax. 

Currently missing joint RoM's do not prevent the pre_processor from running, if a value in the worksheet RoM table is left blank the pre_processor will gracefully set the joint to limitless RoM and throw a warning error when the program executes.

With the deployment of the pre_processor, precision in the model is now tunable via edits to the pre_processor, it is currently set at twelve decimal places. 

The hip architecture is the non-coupled orientation with axes "0 -1 0", "1 0 0", and "0 0 1" (right hip) in mjc coordinated. The coupled config will follow as a variant. The decision to prioritize non-coupled first arises from the goal of obtaining a working model as quickly as possible. Both architectures will eventually be constructed so no time is wasted by building the non-coupled, and we expect time to be saved by learning MuJoCo on a simpler scope and then exanding to the target coupled configuration. The spine architecture is modelled as three rigid segments: pelvis, abdomen, thorax. Initially the roms are unlimited as the reference doc currently does not include those values, but each has a FIXME comment beside it so they do not slip through the cracks. 

The worksheet has been amended, the "mujoco" column (where the pre_processor pulls from) now preferentially chooses values from the "freyja" column and uses ceiling values if the "freyja" value is left blank. This allows us to override the ceiling values without changing that column, currently in use for ankle dorsiflexion. 

Joint axes are hardcoded into the MJCF model as they are invariant. Axes use the MJC coordinate system. <geom> sizes are currently hardcoded. A future update will build out a table for them to live in within the sheet, linked to the pre_processor to make them parametric. As pure visual aids this is low priority but they should eventually be driven by segment lengths (e.g. the thigh capsule size depends on thigh length).


FIXME: still need to execute: The product-of-inertia sign convention is resolved against the Dumas 2007 inertia-matrix equation and against MuJoCo's own off-diagonal convention; the memo states the convention adopted and the test that confirmed it.

A world-frame quantity computed by MuJoCo (e.g. that segment's CoM position in a known pose) matches an independent calculation to within 1 mm.

Test joint conventions using a script

Static gravity check. With the pelvis held and all joint velocities and accelerations zero, the joint torques MuJoCo's inverse dynamics reports for at least two postures — neutral standing, and one with substantial hip and knee flexion — match an independent calculation that does not use MuJoCo, to within 1%.

Add versions. 
The repo at a specific commit. Give me a tag or hash in the memo, so I'm reviewing exactly what you tested and not whatever main looks like later.
A README that works for a stranger. It covers environment setup, how to run the check script, and how to set up credentials if someone wants to regenerate the model. Following it should be all a cold reader needs.
A reproduction record in the memo. It should have the commands you ran in a fresh directory, the Python and package versions, and the check output from that run, with a short note that the run needed no sheet or credentials. Paste real output, not a description of it.
Commit history that tells the story. I'm reading the log, so this is not just the final state.