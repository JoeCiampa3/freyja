**Build**

Sprint 1 and 1b focus on creating and evaluating the first iteration of the Freyja MuJoCo model. This model will eventually be used for everything from inverse kinematic driven actuator choices to simulating fall impacts and designing and testing controllers.

The model contains sixteen rigid segments. Lengths and inertial data are sourced from the ground truth anthropometric reference document. All major joints have been built in with the exception of fingers and toes. Several joints have been simplied for the initial version (see deviations). Simple geometry such as capsules, spheres, and elipses are used for visual aid and will eventually be replaced by the segment meshes. 

To avoid manual transcription error, every value (eg segment masses, lengths, joint roms,...) in the MJC model is pulled directly from the ground truth Anthropometric Reference sheet and pushed to the model. The vehicle for this is the Python program pre_processor in scripts\ which is now complete. It was initially human written until it was tested and working for BSIP data, the remaining work was deligated to Claude Code to expand the functionality to include RoM and position data. In addition, it was further fleshed out with checks, failsafes, and quality of life upgrades (writing to a designated model file when broken, publishing param CSVs to an archive, etc), but the core loop was written and understood by the creator. At this point in time the program is fully functional and the only human interaction in the sheet to model pipeline is to run the pre_processor, which will eventually be automated away (currently low priority but will prevent accidental mismatches from forgetting to run pre_processor by updating the model live post sheet-update). models\freyja_template.xml is the true model that is maintained and iterated, when ready to use the models\scripts\freyja.xml (the frontend model) the command line is used to run the pre_processor which pulls values from the sheet, checks and sanitizes them, reads from the template, and wherever a ${placeholder} is within the template it is replaced by the sheet value.

The current state of the model is simple but complete, with a robust pipeline from reference doc to model that makes basic iterations trivial.

**Assumptions**

**Validations**

Validations this sprint lived in testing the pre_processor and the physical properties of the model. 

After returning to Dumas 2007, the spreadsheet mass closes to within 0.1% (64.935kg compared to target 65kg, discrepancy explained by rounding in Dumas' published segment mass fractions). The pre_processor contains a built in mass check every time it is run, and an independent python file importing the MJC model and evaluating the whole-body mass both agree on 64.935kg, exactly matching the sheets mass. We have concluded there is no perceptible mass loss through the transcription pipeline. 


**Deviations**
FIXME: explain joint simplifications for knee, ankle, wrist, spine, shoulders, etc.

Currently missing joint RoM's do not prevent the pre_processor from running, if a value in the worksheet RoM table is left blank the pre_processor will gracefully set the joint to limitless rom and throw a warning error when the program executes.

With the deployment of the pre_processor, precision in the model is now tunable via edits to the pre_processor, it is currently set at twelve decimal places. 

The hip architecture is the non-coupled orientation with axes "0 -1 0", "1 0 0", and "0 0 1" (right hip) in mjc coordinated. The coupled config will follow as a variant. The decision to prioritize non-coupled first arises from the goal of obtaining a working model as quickly as possible. Both architectures will eventually be constructed so no time is wasted by building the non-coupled, and we expect time to be saved by learning MuJoCo on a simpler scope and then exanding to the target coupled configuration. The spine architecture is modelled as three rigid segments: pelvis, abdomen, thorax. Initially the roms are unlimited as the reference doc currently does not include those values, but each has a FIXME comment beside it so they do not slip through the cracks. 



This sprint serves as an addendum to complete the goals from the last sprint. This memo will lay out the current build, validations, limitations, and assumptions made during the sprint.

The main blocker last sprint was criterion 1, traceability. Several other criteria lie downstream so locking it in was the first focus of this sprint. 

The main limitation of the pre_processor is fragility, if the sheet name/ID or cell names change it will break the connection to the Python program. It will fail loudly, but we can no longer start a new sheet after every edit Claude makes. To get around this we intend to make a new Python program that will take edits Claude makes to a local xlsx file and automatically push them to the sheet. 


The pipeline from sheet to model begins with directly sourced biomechanics data in the relevant worksheet (eg BSIP worksheet uses Dumas), ISB coordinates (x anterior z to right, y superior) are used throughout. MuJoCo uses a different coordinate system, which requires the transform (x, y, z) (ISB) -> (x', y', z') = (x, -z, y) (MJC). This transformation is applied within the worksheet itself, all transformed data is put into MuJoCo specific worksheets to be pulled by the pre_processor. For example, the pelvis has its mass, length, and inertial parameters sourced directly from Dumas 2007 and normalized in the sheet with Freyja's target mass and stature. Updating those values parametrically updates each quantity they drive. The values are in ISB coordinates, so within the sheet they are transformed into MuJoCo coordinates and placed into a MJC specific worksheet via linked cells to preserve the parametric nature of the pipeline. The transformation swaps CoM_y with CoM_z and flips the sign of the latter. It flips Iyy and Izz (no change in sign because these are diagonal inertia tensor elements), and flips Ixy with Ixz and changes the sign of Ixz and Iyz. The MuJoCo sheet also alters the order of inertia entries to Ixx Iyy Izz Ixy Ixz Iyz to match the order MuJoCo's <inertial> entity expects. After updating any value within the worksheet, the pre_processor is run (currently by hand later we plan to make it trigger automatically) and pulls all relevant data from the MJC worksheet tables, mirrors bilateral segments, reads the freyja_template.xml model and writes it to the freyja.xml. As it does so every ${placeholder} written into the template is replaced by the corresponding value pulled from the worksheet.

Joint axes are hardcoded into the MJCF model as they are invariant. Axes use the MJC coordinate system. <geom> sizes are currently hardcoded. A future update will build out a table for them to live in within the sheet, linked to the pre_processor to make them parametric. As pure visual aids this is low priority but they should eventually be driven by segment lengths (e.g. the thigh capsule size depends on thigh length).

Current items to be addressed in the future: building automatic pre_processor launch on sheet edit. Deciding how to best model the knees ICR and whether the knee and ankle need their # of dofs expanded or if the current system will produce results with sufficiently small simulation and visual error. 