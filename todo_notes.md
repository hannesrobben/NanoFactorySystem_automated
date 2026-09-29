# Todo and note inventory

Created for T19 on 2026-09-29. It records every work marker (TODO, ToDo, FIXME, hotfix) that was removed
from the active code (`nanofactorysystem/`, `mains/`, `test/`; legacy code excluded), plus the slicer
roadmap `nanofactorysystem/aerobasic/slicer/TODO.txt`, which was deleted. Explanatory notes (e.g.
`# Note: …` comments and docstring paragraphs) were left in the code (maintainer decision).

- **Original**: the text as it was in the code (German kept verbatim).
- **Meaning**: what it asks for, in English.
- **Locations**: `file:line` before the removal. Many experiment scripts in `mains/` are copies of the
  template, so the same marker appears in many files.
- **Package**: the work package at the end of this file that covers it.

## Inventory

### N001 — T26

Original:
```text
# ToDo(HR): how do i transfer a dict or other system arguments to this function?
```
Meaning: Experiment scripts: find a better way to pass `sys_args` and other system arguments to the print function than a module-level dict.

<details><summary>Locations (37)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:46`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:46`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:48`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:49`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:49`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:49`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:48`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:48`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:48`
- `mains/Experiments/Grating_63/binary_grating_test1.py:47`
- `mains/Experiments/Grating_63/coordinate_test.py:48`
- `mains/Experiments/Grating_63/grid_point_test.py:47`
- `mains/Experiments/Grating_63/parameter_test.py:47`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:47`
- `mains/Experiments/Grating_63/realignment_grating.py:48`
- `mains/Experiments/Grating_63/test_program_cycle.py:47`
- `mains/Experiments/Grating_63/test_stitching.py:47`
- `mains/Experiments/IFOV_63/ifov_test.py:46`
- `mains/Experiments/Kailas/grating_ifov_big.py:46`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:46`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:46`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:46`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:47`
- `mains/Experiments/Model_3D_experiment.py:44`
- `mains/Experiments/default_exp_file.py:47`
- `mains/Experiments/other/parameter_testprint.py:42`
- `mains/Experiments/other/parameter_testprint_slicing_hatching.py:42`
- `mains/Experiments/other/qr_code_investigation.py:43`
- `mains/Experiments/other/testprint_dhm.py:45`
- `mains/Experiments/other/testprint_dhm2.py:46`
- `mains/Experiments/other/testprint_dhm3.py:46`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:47`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed.py:46`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed_test4orientation.py:46`
- `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py:42`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:47`
- `mains/Experiments/stacked/stacked_lenses_test.py:48`

</details>

### N002 — T26

Original:
```text
# ToDo: DropDirection noch mit übergeben und testen ob das funktioniert
```
Meaning: Pass the DropDirection as a parameter of the print function as well, and test that it works.

<details><summary>Locations (46)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:60`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:60`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:62`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:63`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:63`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:63`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:62`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:62`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:62`
- `mains/Experiments/Grating_63/binary_grating_test1.py:61`
- `mains/Experiments/Grating_63/coordinate_test.py:62`
- `mains/Experiments/Grating_63/grid_point_test.py:61`
- `mains/Experiments/Grating_63/parameter_test.py:61`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:61`
- `mains/Experiments/Grating_63/realignment_grating.py:62`
- `mains/Experiments/Grating_63/test_program_cycle.py:61`
- `mains/Experiments/Grating_63/test_stitching.py:61`
- `mains/Experiments/IFOV_63/ifov_test.py:60`
- `mains/Experiments/Kailas/grating_ifov_big.py:60`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:60`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:60`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:60`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:61`
- `mains/Experiments/Kailas/lens_surface_test.py:60`
- `mains/Experiments/Kailas/lenses.py:60`
- `mains/Experiments/Kailas/padding_test_0_5mm.py:60`
- `mains/Experiments/Model_3D_experiment.py:68`
- `mains/Experiments/default_exp_file.py:66`
- `mains/Experiments/dhm/dhm_img_4_SEM.py:60`
- `mains/Experiments/dhm/dhm_paper.py:60`
- `mains/Experiments/dhm/dhm_paper_aligning_DHM_camera.py:60`
- `mains/Experiments/dhm/dhm_paper_power_refractiveIndex.py:60`
- `mains/Experiments/dhm/dhm_paper_voxel_axial.py:60`
- `mains/Experiments/other/dhm_paper_print.py:59`
- `mains/Experiments/other/parameter_testprint.py:56`
- `mains/Experiments/other/parameter_testprint_slicing_hatching.py:56`
- `mains/Experiments/other/qr_code_investigation.py:57`
- `mains/Experiments/other/testprint_dhm.py:59`
- `mains/Experiments/other/testprint_dhm2.py:60`
- `mains/Experiments/other/testprint_dhm3.py:60`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:61`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed.py:60`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed_test4orientation.py:60`
- `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py:56`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:61`
- `mains/Experiments/stacked/stacked_lenses_test.py:62`

</details>

### N003 — T27

Original:
```text
# ToDo: Has to be changed in future in order to allow more prints of the same experiment on one substrate without
# deleting all the different data of previous prints
```
Meaning: The output path must allow several prints of the same experiment on one substrate without deleting the data of previous prints.

<details><summary>Locations (46)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:62`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:62`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:64`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:65`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:65`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:65`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:64`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:64`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:64`
- `mains/Experiments/Grating_63/binary_grating_test1.py:63`
- `mains/Experiments/Grating_63/coordinate_test.py:64`
- `mains/Experiments/Grating_63/grid_point_test.py:63`
- `mains/Experiments/Grating_63/parameter_test.py:63`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:63`
- `mains/Experiments/Grating_63/realignment_grating.py:64`
- `mains/Experiments/Grating_63/test_program_cycle.py:63`
- `mains/Experiments/Grating_63/test_stitching.py:63`
- `mains/Experiments/IFOV_63/ifov_test.py:62`
- `mains/Experiments/Kailas/grating_ifov_big.py:62`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:62`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:62`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:62`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:63`
- `mains/Experiments/Kailas/lens_surface_test.py:62`
- `mains/Experiments/Kailas/lenses.py:62`
- `mains/Experiments/Kailas/padding_test_0_5mm.py:62`
- `mains/Experiments/Model_3D_experiment.py:73`
- `mains/Experiments/default_exp_file.py:68`
- `mains/Experiments/dhm/dhm_img_4_SEM.py:62`
- `mains/Experiments/dhm/dhm_paper.py:62`
- `mains/Experiments/dhm/dhm_paper_aligning_DHM_camera.py:62`
- `mains/Experiments/dhm/dhm_paper_power_refractiveIndex.py:62`
- `mains/Experiments/dhm/dhm_paper_voxel_axial.py:62`
- `mains/Experiments/other/dhm_paper_print.py:61`
- `mains/Experiments/other/parameter_testprint.py:58`
- `mains/Experiments/other/parameter_testprint_slicing_hatching.py:58`
- `mains/Experiments/other/qr_code_investigation.py:59`
- `mains/Experiments/other/testprint_dhm.py:61`
- `mains/Experiments/other/testprint_dhm2.py:62`
- `mains/Experiments/other/testprint_dhm3.py:62`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:63`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed.py:62`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed_test4orientation.py:62`
- `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py:58`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:63`
- `mains/Experiments/stacked/stacked_lenses_test.py:64`

</details>

### N004 — T27

Original:
```text
# ToDo(HR) Adjust referencing to another more suitable path
```
Meaning: Use a more suitable default location for the output folder than `.output/...`.

<details><summary>Locations (46)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:65`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:65`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:67`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:68`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:68`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:68`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:67`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:67`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:67`
- `mains/Experiments/Grating_63/binary_grating_test1.py:66`
- `mains/Experiments/Grating_63/coordinate_test.py:67`
- `mains/Experiments/Grating_63/grid_point_test.py:66`
- `mains/Experiments/Grating_63/parameter_test.py:66`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:66`
- `mains/Experiments/Grating_63/realignment_grating.py:67`
- `mains/Experiments/Grating_63/test_program_cycle.py:66`
- `mains/Experiments/Grating_63/test_stitching.py:66`
- `mains/Experiments/IFOV_63/ifov_test.py:65`
- `mains/Experiments/Kailas/grating_ifov_big.py:65`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:65`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:65`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:65`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:66`
- `mains/Experiments/Kailas/lens_surface_test.py:65`
- `mains/Experiments/Kailas/lenses.py:65`
- `mains/Experiments/Kailas/padding_test_0_5mm.py:65`
- `mains/Experiments/Model_3D_experiment.py:76`
- `mains/Experiments/default_exp_file.py:71`
- `mains/Experiments/dhm/dhm_img_4_SEM.py:65`
- `mains/Experiments/dhm/dhm_paper.py:65`
- `mains/Experiments/dhm/dhm_paper_aligning_DHM_camera.py:65`
- `mains/Experiments/dhm/dhm_paper_power_refractiveIndex.py:65`
- `mains/Experiments/dhm/dhm_paper_voxel_axial.py:65`
- `mains/Experiments/other/dhm_paper_print.py:64`
- `mains/Experiments/other/parameter_testprint.py:61`
- `mains/Experiments/other/parameter_testprint_slicing_hatching.py:61`
- `mains/Experiments/other/qr_code_investigation.py:62`
- `mains/Experiments/other/testprint_dhm.py:64`
- `mains/Experiments/other/testprint_dhm2.py:65`
- `mains/Experiments/other/testprint_dhm3.py:65`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:66`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed.py:65`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed_test4orientation.py:65`
- `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py:61`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:66`
- `mains/Experiments/stacked/stacked_lenses_test.py:67`

</details>

### N005 — T27

Original:
```text
# ToDo(HR) make ist more controllable
```
Meaning: Make the output path handling more controllable.

<details><summary>Locations (29)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:68`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:68`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:70`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:71`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:71`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:71`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:70`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:70`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:70`
- `mains/Experiments/Grating_63/binary_grating_test1.py:69`
- `mains/Experiments/Grating_63/coordinate_test.py:70`
- `mains/Experiments/Grating_63/grid_point_test.py:69`
- `mains/Experiments/Grating_63/parameter_test.py:69`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:69`
- `mains/Experiments/Grating_63/realignment_grating.py:70`
- `mains/Experiments/Grating_63/test_program_cycle.py:69`
- `mains/Experiments/Grating_63/test_stitching.py:69`
- `mains/Experiments/IFOV_63/ifov_test.py:68`
- `mains/Experiments/Kailas/grating_ifov_big.py:68`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:68`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:68`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:68`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:69`
- `mains/Experiments/Model_3D_experiment.py:84`
- `mains/Experiments/default_exp_file.py:74`
- `mains/Experiments/other/qr_code_investigation.py:65`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:69`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:69`
- `mains/Experiments/stacked/stacked_lenses_test.py:70`

</details>

### N006 — T26

Original:
```text
# ToDo change fov to structure size and add fov to real
```
Meaning: Use the structure size instead of the FOV and pass the real FOV separately.

<details><summary>Locations (25)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:148`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:150`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:151`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:151`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:151`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:149`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:149`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:149`
- `mains/Experiments/Grating_63/binary_grating_test1.py:147`
- `mains/Experiments/Grating_63/coordinate_test.py:148`
- `mains/Experiments/Grating_63/grid_point_test.py:148`
- `mains/Experiments/Grating_63/parameter_test.py:147`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:147`
- `mains/Experiments/Grating_63/realignment_grating.py:149`
- `mains/Experiments/Grating_63/test_program_cycle.py:154`
- `mains/Experiments/Grating_63/test_stitching.py:147`
- `mains/Experiments/IFOV_63/ifov_test.py:148`
- `mains/Experiments/Kailas/grating_ifov_big.py:148`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:153`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:153`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:153`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:154`
- `mains/Experiments/Kailas/lens_surface_test.py:158`
- `mains/Experiments/Kailas/lenses.py:157`
- `mains/Experiments/Kailas/padding_test_0_5mm.py:148`

</details>

### N007 — T26

Original:
```text
# ToDo: changing depending on experiment - e.g. (number of repetitions, number of structures)
```
Meaning: The grid (number of repetitions × number of structures) must depend on the experiment instead of being hardcoded.

<details><summary>Locations (31)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:153`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:153`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:155`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:156`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:156`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:156`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:154`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:154`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:154`
- `mains/Experiments/Grating_63/binary_grating_test1.py:152`
- `mains/Experiments/Grating_63/coordinate_test.py:153`
- `mains/Experiments/Grating_63/grid_point_test.py:153`
- `mains/Experiments/Grating_63/parameter_test.py:152`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:152`
- `mains/Experiments/Grating_63/realignment_grating.py:154`
- `mains/Experiments/Grating_63/test_program_cycle.py:159`
- `mains/Experiments/Grating_63/test_stitching.py:152`
- `mains/Experiments/IFOV_63/ifov_test.py:153`
- `mains/Experiments/Kailas/grating_ifov_big.py:153`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:158`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:158`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:158`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:159`
- `mains/Experiments/Kailas/lens_surface_test.py:163`
- `mains/Experiments/Kailas/lenses.py:162`
- `mains/Experiments/Kailas/padding_test_0_5mm.py:153`
- `mains/Experiments/Model_3D_experiment.py:174`
- `mains/Experiments/default_exp_file.py:158`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:154`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:153`
- `mains/Experiments/stacked/stacked_lenses_test.py:153`

</details>

### N008 — T26

Original:
```text
# ToDo changing depending on experiment
```
Meaning: `n_mid_points` (and similar grid values) must depend on the experiment instead of being hardcoded.

<details><summary>Locations (47)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:154`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:154`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:156`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:157`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:157`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:157`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:155`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:155`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:155`
- `mains/Experiments/Grating_63/binary_grating_test1.py:153`
- `mains/Experiments/Grating_63/coordinate_test.py:154`
- `mains/Experiments/Grating_63/grid_point_test.py:154`
- `mains/Experiments/Grating_63/parameter_test.py:153`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:153`
- `mains/Experiments/Grating_63/realignment_grating.py:155`
- `mains/Experiments/Grating_63/test_program_cycle.py:160`
- `mains/Experiments/Grating_63/test_stitching.py:153`
- `mains/Experiments/IFOV_63/ifov_test.py:154`
- `mains/Experiments/Kailas/grating_ifov_big.py:154`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:159`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:159`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:159`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:160`
- `mains/Experiments/Kailas/lens_surface_test.py:164`
- `mains/Experiments/Kailas/lenses.py:163`
- `mains/Experiments/Kailas/padding_test_0_5mm.py:154`
- `mains/Experiments/Model_3D_experiment.py:175`
- `mains/Experiments/default_exp_file.py:159`
- `mains/Experiments/dhm/dhm_img_4_SEM.py:160`
- `mains/Experiments/dhm/dhm_paper.py:160`
- `mains/Experiments/dhm/dhm_paper_aligning_DHM_camera.py:162`
- `mains/Experiments/dhm/dhm_paper_power_refractiveIndex.py:160`
- `mains/Experiments/dhm/dhm_paper_voxel_axial.py:159`
- `mains/Experiments/other/dhm_paper_print.py:152`
- `mains/Experiments/other/parameter_testprint.py:139`
- `mains/Experiments/other/parameter_testprint_slicing_hatching.py:142`
- `mains/Experiments/other/qr_code_investigation.py:140`
- `mains/Experiments/other/testprint_dhm.py:130`
- `mains/Experiments/other/testprint_dhm2.py:131`
- `mains/Experiments/other/testprint_dhm3.py:133`
- `mains/Experiments/other/z_line_focal_points.py:117`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:155`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed.py:154`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed_test4orientation.py:147`
- `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py:148`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:154`
- `mains/Experiments/stacked/stacked_lenses_test.py:154`

</details>

### N009 — T28

Original:
```text
# TODO: Take image of whole scene
```
Meaning: Take an overview image of the whole scene before and after printing (code is commented out).

<details><summary>Locations (98)</summary>

- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:179`
- `mains/Experiments/Big_substrate_20x/grating_ifov_test.py:227`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:179`
- `mains/Experiments/DHM_tomography/hollow_rect_first_print_63xobj.py:222`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:180`
- `mains/Experiments/Grating_20x/grating_big_stitching.py:231`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:181`
- `mains/Experiments/Grating_20x/plane_fitting_20x.py:248`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:181`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x.py:248`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:183`
- `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:275`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:179`
- `mains/Experiments/Grating_63/Angle_test_NO_hatching.py:232`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:179`
- `mains/Experiments/Grating_63/Angle_test_with_hatching.py:232`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:179`
- `mains/Experiments/Grating_63/FOV_Stitch_test.py:232`
- `mains/Experiments/Grating_63/binary_grating_test1.py:176`
- `mains/Experiments/Grating_63/binary_grating_test1.py:359`
- `mains/Experiments/Grating_63/coordinate_test.py:178`
- `mains/Experiments/Grating_63/coordinate_test.py:255`
- `mains/Experiments/Grating_63/grid_point_test.py:178`
- `mains/Experiments/Grating_63/grid_point_test.py:232`
- `mains/Experiments/Grating_63/parameter_test.py:177`
- `mains/Experiments/Grating_63/parameter_test.py:252`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:177`
- `mains/Experiments/Grating_63/parameter_test_hatching_slicing.py:253`
- `mains/Experiments/Grating_63/realignment_grating.py:179`
- `mains/Experiments/Grating_63/realignment_grating.py:233`
- `mains/Experiments/Grating_63/test_program_cycle.py:184`
- `mains/Experiments/Grating_63/test_program_cycle.py:293`
- `mains/Experiments/Grating_63/test_stitching.py:177`
- `mains/Experiments/Grating_63/test_stitching.py:252`
- `mains/Experiments/IFOV_63/ifov_test.py:179`
- `mains/Experiments/IFOV_63/ifov_test.py:227`
- `mains/Experiments/Kailas/grating_ifov_big.py:179`
- `mains/Experiments/Kailas/grating_ifov_big.py:227`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:184`
- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:233`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:184`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:233`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:184`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:233`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:185`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:228`
- `mains/Experiments/Kailas/lens_surface_test.py:189`
- `mains/Experiments/Kailas/lens_surface_test.py:233`
- `mains/Experiments/Kailas/lenses.py:188`
- `mains/Experiments/Kailas/lenses.py:231`
- `mains/Experiments/Kailas/padding_test_0_5mm.py:179`
- `mains/Experiments/Kailas/padding_test_0_5mm.py:220`
- `mains/Experiments/Model_3D_experiment.py:205`
- `mains/Experiments/Model_3D_experiment.py:253`
- `mains/Experiments/default_exp_file.py:186`
- `mains/Experiments/default_exp_file.py:227`
- `mains/Experiments/dhm/dhm_img_4_SEM.py:185`
- `mains/Experiments/dhm/dhm_img_4_SEM.py:281`
- `mains/Experiments/dhm/dhm_paper.py:185`
- `mains/Experiments/dhm/dhm_paper.py:277`
- `mains/Experiments/dhm/dhm_paper_aligning_DHM_camera.py:187`
- `mains/Experiments/dhm/dhm_paper_aligning_DHM_camera.py:278`
- `mains/Experiments/dhm/dhm_paper_power_refractiveIndex.py:185`
- `mains/Experiments/dhm/dhm_paper_power_refractiveIndex.py:227`
- `mains/Experiments/dhm/dhm_paper_voxel_axial.py:184`
- `mains/Experiments/dhm/dhm_paper_voxel_axial.py:226`
- `mains/Experiments/other/dhm_paper_print.py:173`
- `mains/Experiments/other/dhm_paper_print.py:265`
- `mains/Experiments/other/parameter_testprint.py:159`
- `mains/Experiments/other/parameter_testprint.py:240`
- `mains/Experiments/other/parameter_testprint_slicing_hatching.py:162`
- `mains/Experiments/other/parameter_testprint_slicing_hatching.py:253`
- `mains/Experiments/other/qr_code_investigation.py:161`
- `mains/Experiments/other/qr_code_investigation.py:344`
- `mains/Experiments/other/testprint_dhm.py:150`
- `mains/Experiments/other/testprint_dhm.py:406`
- `mains/Experiments/other/testprint_dhm2.py:152`
- `mains/Experiments/other/testprint_dhm2.py:378`
- `mains/Experiments/other/testprint_dhm3.py:154`
- `mains/Experiments/other/testprint_dhm3.py:410`
- `mains/Experiments/other/z_line_focal_points.py:138`
- `mains/Experiments/other/z_line_focal_points.py:180`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:181`
- `mains/Experiments/parameter_study/line_test/Power_speed_line_test.py:228`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed.py:176`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed.py:220`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed_test4orientation.py:168`
- `mains/Experiments/parameter_study/parameter_testprint_power_speed_test4orientation.py:246`
- `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py:169`
- `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py:260`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:179`
- `mains/Experiments/refractive_index/refractive_index_vel_power.py:220`
- `mains/Experiments/stacked/stacked_lenses_test.py:177`
- `mains/Experiments/stacked/stacked_lenses_test.py:252`
- `mains/dhm_paper.py:93`
- `mains/dhm_paper.py:174`
- `mains/dhm_paper_pillowProblem_63.py:102`
- `mains/dhm_paper_pillowProblem_63.py:268`

</details>

### N010 — T37

Original:
```text
# Wert für 20x - ToDO für 63x genauso?
```
Meaning: The focus detection value was tuned for 20x; check whether the same value works for 63x.

Locations: `mains/Experiments/Grating_20x/plane_fitting_20x.py:38`, `mains/Experiments/Grating_20x/zumLaufBringen_20x_grating.py:38`

### N011 — T27

Original:
```text
# todo save substrate
```
Meaning: Pass and store the substrate information (it was not passed on).

<details><summary>Locations (4)</summary>

- `mains/Experiments/Kailas/ifovGrating_diffPower_500um.py:140`
- `mains/Experiments/Kailas/ifovGrating_diffPower_75um.py:140`
- `mains/Experiments/Kailas/ifovGrating_noPower_differentSize.py:140`
- `mains/Experiments/Kailas/ifovLens_diffSlice_75um.py:141`

</details>

### N012 — T31

Original:
```text
# ToDo implmentieren, dass auch power gewechselt werden kann
```
Meaning: Parameter test prints: allow changing the laser power between structures.

Locations: `mains/Experiments/other/parameter_testprint.py:111`, `mains/Experiments/other/parameter_testprint_slicing_hatching.py:113`, `mains/Experiments/parameter_study/parameter_testprint_slicing_hatching.py:113`

### N013 — T26

Original:
```text
# ToDo: changing depending on experiment
```
Meaning: The grid values must depend on the experiment instead of being hardcoded.

Locations: `mains/Experiments/other/qr_code_investigation.py:139`, `mains/Experiments/other/z_line_focal_points.py:116`

### N014 — T36

Original:
```text
# ToDo Put this in front of the area where the zline matrix is executed
```
Meaning: Z-line focal point script: move this block in front of the area where the z-line matrix is executed.

Locations: `mains/Experiments/other/z_line_focal_points.py:199`

### N015 — T36

Original:
```text
# ToDo add further information's to the dictionary
```
Meaning: Z-line focal point script: add further information to the result dictionary.

Locations: `mains/Experiments/other/z_line_focal_points.py:239`

### N016 — T36

Original:
```text
# ToDo : Check if dz will be split in half or if it will be printed continuously
```
Meaning: Check whether the z-line length dz is split in half around z or printed from z onwards.

Locations: `mains/Experiments/other/z_line_focal_points.py:260`

### N017 — T36

Original:
```text
# ToDo: probably recalculate z with dz/2
```
Meaning: Probably recalculate z with dz/2 (depends on the check above).

Locations: `mains/Experiments/other/z_line_focal_points.py:261`

### N018 — T36

Original:
```text
# ToDo:
#   - define min_distance
#   - define different dz -- maybe also with an additional noise parameter so that it is always somewhat different
#   - define boundary -- important
#   - implement all the other variable etc above this methods in the script
```
Meaning: Z-line focal point script: define min_distance, different dz values (possibly with a noise parameter), the boundary (important), and move all variables above the methods.

Locations: `mains/Experiments/other/z_line_focal_points.py:301`

### N019 — T36

Original:
```text
# todo check if z_line_zdc_path already exists
```
Meaning: Check whether `z_line_zdc_path` already exists before writing.

Locations: `mains/Experiments/other/z_line_focal_points.py:346`

### N020 — T36

Original:
```text
# ToDo : add noise here , so the dz's are all a little bit different
```
Meaning: Add noise to the dz values so that they all differ slightly.

Locations: `mains/Experiments/other/z_line_focal_points.py:353`

### N021 — T26

Original:
```text
# TODO: Determine automatically
```
Meaning: DHM paper script: determine this value automatically instead of hardcoding it.

Locations: `mains/dhm_paper.py:47`, `mains/dhm_paper_pillowProblem_63.py:54`

### N022 — T29

Original:
```text
# ToDo: Make sure center is within the edges
# assert center.Y in [ymin, ymax]
# assert center.X in [xmin, xmax]
```
Meaning: Validate that the experiment center lies within the resin drop edges (asserts were commented out).

<details><summary>Locations (4)</summary>

- `mains/grating_try.py:26`
- `mains/main.py:35`
- `mains/main_3D_model.py:22`
- `mains/main_IFOV.py:45`

</details>

### N023 — T28

Original:
```text
# ToDo: Get a timelogger or a overview on how long it will take
```
Meaning: Add a time logger or an overview of how long an experiment will take.

<details><summary>Locations (4)</summary>

- `mains/grating_try.py:43`
- `mains/main.py:61`
- `mains/main_3D_model.py:50`
- `mains/main_IFOV.py:71`

</details>

### N024 — T27

Original:
```text
# ToDo 1: identification for substrate to track the printing of different experiments on one substrate
```
Meaning: Identify the substrate, to track the printing of different experiments on one substrate.

<details><summary>Locations (4)</summary>

- `mains/grating_try.py:47`
- `mains/main.py:65`
- `mains/main_3D_model.py:54`
- `mains/main_IFOV.py:75`

</details>

### N025 — T27

Original:
```text
# ToDo 2: Build a custom experiment database based on different identification factors (e.g. substrate, date, objective etc)
```
Meaning: Build an experiment database based on identification factors (substrate, date, objective, …).

<details><summary>Locations (4)</summary>

- `mains/grating_try.py:48`
- `mains/main.py:66`
- `mains/main_3D_model.py:55`
- `mains/main_IFOV.py:76`

</details>

### N026 — T29

Original:
```text
# ToDo 3: Plane Fitting: change to a "just border" mode and the currently used mode (Between each FOV of a print)
```
Meaning: Plane fitting: add a "border only" mode next to the current mode (between each FOV of a print).

<details><summary>Locations (4)</summary>

- `mains/grating_try.py:49`
- `mains/main.py:67`
- `mains/main_3D_model.py:56`
- `mains/main_IFOV.py:77`

</details>

### N027 — T30

Original:
```text
# todo
#       create dictionary for restarting experiment  - alles was am anfang dem Experiment übergeben wird
#       übergabe von restart sollte eigentlich nur die ordner struktur sein
#       zusätzlich muss außerdem noch die substrat informationen im hauptordner gegeben werden
#       !!! Experiment bekommt immer eine neue UUID - das sollte nicht sein!
```
Meaning: Restart: the restart should only need the folder structure (done in T25 via experiment_dictionary.json); the substrate information must be available in the main folder; an experiment must keep its UUID when restarted instead of getting a new one.

Locations: `mains/restart_experiment.py:16`

### N028 — T30

Original:
```text
# todo nochmal kontrollieren, wenn er bereits eine oder zwis schichten gedruckt hat - sieht so aus, dass es nicht an der richtigen stelle wieder startet!
# wahrscheinlich liegt es daran, wenn das abbricht nachdem man bereits einmal wieder aufgestartete hat, dann wird die anzahl der layer geändert
```
Meaning: Restart: check the resume position when one or two layers were already printed; it seems not to restart at the right layer, probably when a print is aborted again after a restart, because the layer count changes.

Locations: `mains/restart_experiment.py:27`

### N029 — T32

Original:
```text
# ToDo(hrobben): programm associate muss überarbeitet werden, da die Syntax des befehls nicht korrekt ist
```
Meaning: AeroBasic API: `PROGRAM_ASSOCIATE` must be reworked, the command syntax is not correct.

Locations: `nanofactorysystem/aerobasic/__init__.py:121`

### N030 — T32

Original:
```text
# TODO: How to get system parameters?
```
Meaning: AeroBasic API: how to read system parameters?

Locations: `nanofactorysystem/aerobasic/__init__.py:452`

### N031 — T32

Original:
```text
# TODO(dwoiwode): Make compact even more compact by multiple variable declarations per line
```
Meaning: Program text: make the compact output even more compact (several variable declarations per line).

Locations: `nanofactorysystem/aerobasic/programs/__init__.py:98`

### N032 — T32

Original:
```text
# TODO(dwoiwode): More metadata?
```
Meaning: Program text: add more metadata to the header.

Locations: `nanofactorysystem/aerobasic/programs/__init__.py:102`

### N033 — T32

Original:
```text
# TODO: Mode check for e.g. VELOCITY ON, ABSOLUTE, ...
```
Meaning: Program: check modes such as VELOCITY ON or ABSOLUTE.

Locations: `nanofactorysystem/aerobasic/programs/__init__.py:146`

### N034 — T33

Original:
```text
ToDo(HR) algorithm
```
Meaning: DOE: the algorithm is still missing (docstring).

Locations: `nanofactorysystem/aerobasic/programs/drawings/DOE.py:155`

### N035 — T33

Original:
```text
# todo future - make the axis on which the grating is orientated parameterized
```
Meaning: Gratings/DOE: make the axis along which the grating is oriented a parameter.

Locations: `nanofactorysystem/aerobasic/programs/drawings/DOE.py:199`, `nanofactorysystem/aerobasic/programs/drawings/gratings.py:28`, `nanofactorysystem/aerobasic/programs/drawings/gratings.py:175`

### N036 — T33

Original:
```text
# todo: überlegen wie man es besser macht: gesamtbreite und periode oder breite von Berg & Tal sowie n_periode um gesamtbreite zu berechnen
```
Meaning: Gratings/DOE: decide on the better parameterisation: total width and period, or widths of ridge and groove plus the number of periods to compute the total width.

Locations: `nanofactorysystem/aerobasic/programs/drawings/DOE.py:200`, `nanofactorysystem/aerobasic/programs/drawings/gratings.py:29`, `nanofactorysystem/aerobasic/programs/drawings/gratings.py:176`

### N037 — T33

Original:
```text
# todo future: make sure that the structure doesnt exceed full_width! somehow to do with n_grating and number of periods + full max_width grating?
```
Meaning: Gratings/DOE: make sure the structure does not exceed `full_width` (related to n_grating and number of periods).

Locations: `nanofactorysystem/aerobasic/programs/drawings/DOE.py:263`, `nanofactorysystem/aerobasic/programs/drawings/gratings.py:104`

### N038 — T34

Original:
```text
# todo z value has to be assigned correctly
```
Meaning: Stacked lens: assign the z value correctly.

Locations: `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:94`

### N039 — T34

Original:
```text
#todo not ready yet
```
Meaning: Stacked lens: this part is not finished.

Locations: `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:98`

### N040 — T34

Original:
```text
# todo prior space in between + lens height
```
Meaning: Stacked lens: take the gap in between and the lens height into account.

Locations: `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:106`

### N041 — T34

Original:
```text
# todo - check what is x and y in rectangle 3d
```
Meaning: Stacked lens: check what x and y mean in Rectangle3D.

<details><summary>Locations (6)</summary>

- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:236`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:249`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:358`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:371`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:438`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:451`

</details>

### N042 — T34

Original:
```text
# overlap for making sure that it is connected - ??? - todo better way
```
Meaning: Stacked lens: find a better way than an overlap to make sure the parts are connected.

<details><summary>Locations (6)</summary>

- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:237`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:250`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:359`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:372`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:439`
- `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:452`

</details>

### N043 — T34

Original:
```text
#todo change calculation of the iterate layer function is changed (-1 height in between)
```
Meaning: Stacked lens: change the layer calculation once `iterate_layers` changes (-1 height in between).

Locations: `nanofactorysystem/aerobasic/programs/drawings/Stacked_lens.py:304`

### N044 — T32

Original:
```text
# todo investigate ramp types --- available LINEAR SINE SCURVE
```
Meaning: IFOV program setup: investigate the ramp types (LINEAR, SINE, SCURVE).

Locations: `nanofactorysystem/aerobasic/programs/drawings/base.py:52`

### N045 — T32

Original:
```text
# todo(HR) find a good and relatable value
```
Meaning: IFOV program: find a sensible, justified threshold for the speed value F.

Locations: `nanofactorysystem/aerobasic/programs/drawings/base.py:137`

### N046 — T37

Original:
```text
# ToDo(HR) Delete Hotfix and change this - if not attr == "data": if attr == "[NOT FOUND]": continue else: irgendwie die daten abspeichern
```
Meaning: `DrawableObject._init_args`: remove the hotfix and store the "data" attribute properly instead of skipping it.

Locations: `nanofactorysystem/aerobasic/programs/drawings/base.py:434`

### N047 — T33

Original:
```text
# todo mit stitcher
```
Meaning: Gratings: use the stitcher.

Locations: `nanofactorysystem/aerobasic/programs/drawings/gratings.py:43`

### N048 — T33

Original:
```text
# todo !!!!
```
Meaning: Gratings: unexplained urgent todo ("todo !!!!"); needs review.

Locations: `nanofactorysystem/aerobasic/programs/drawings/gratings.py:121`, `nanofactorysystem/aerobasic/programs/drawings/gratings.py:122`

### N049 — T33

Original:
```text
# todo change to usage with tile_boundaries
```
Meaning: Gratings: use the tile boundaries.

Locations: `nanofactorysystem/aerobasic/programs/drawings/gratings.py:135`

### N050 — T33

Original:
```text
# todo
```
Meaning: Gratings: unexplained todo in commented-out code; needs review.

Locations: `nanofactorysystem/aerobasic/programs/drawings/gratings.py:148`

### N051 — T33

Original:
```text
# todo include programm task number to know when new tiles are being printed
```
Meaning: Height function structures: include the program task number to know when new tiles are printed.

Locations: `nanofactorysystem/aerobasic/programs/drawings/height_function_structures/structures.py:273`

### N052 — T33

Original:
```text
# TODO: Implement proper Cohen-Sutherland line clipping
```
Meaning: Height function structures: implement proper Cohen-Sutherland line clipping (currently segments outside the bounds are skipped).

Locations: `nanofactorysystem/aerobasic/programs/drawings/height_function_structures_fixed.py:406`

### N053 — T33

Original:
```text
#note todo
```
Meaning: Height function structures: unexplained note/todo; needs review.

Locations: `nanofactorysystem/aerobasic/programs/drawings/height_function_structures_fixed.py:701`

### N054 — T33

Original:
```text
# create program for base (rectangle) - todo think about aperture in the future
```
Meaning: Height function structures: consider an aperture for the base rectangle in the future.

Locations: `nanofactorysystem/aerobasic/programs/drawings/height_function_structures_fixed.py:711`

### N055 — T33

Original:
```text
# todo - mit polyline auf ifov umschreiben und dann neue berechnung der punkte wie bei hollow structure
#   dient dazu eine andere hatching taktik auszuprobieren-vielleicht möglich die Sachen an den Seiten umzustellen
```
Meaning: IFOV gratings: rewrite with IFOV polylines and recompute the points as in the hollow structure, to try another hatching strategy (possibly rearranging the sides).

Locations: `nanofactorysystem/aerobasic/programs/drawings/ifov_gratings.py:324`

### N056 — T33

Original:
```text
# todo ist das notwendig
```
Meaning: IFOV gratings: is this step necessary?

Locations: `nanofactorysystem/aerobasic/programs/drawings/ifov_gratings.py:458`

### N057 — T33

Original:
```text
# todo (HR) check if it has an influence if LINEAR is used - out of the scope of IFOV should be working
```
Meaning: IFOV gratings: check whether using LINEAR (outside the scope of IFOV) has an influence; it should work.

Locations: `nanofactorysystem/aerobasic/programs/drawings/ifov_gratings.py:462`

### N058 — T32

Original:
```text
# TODO: Better algorithm to determine task_id
```
Meaning: Task handling: better algorithm to choose the task id.

Locations: `nanofactorysystem/aerobasic/programs/drawings/layered_objects.py:119`, `nanofactorysystem/devices/aerotech/__init__.py:179`

### N059 — T34

Original:
```text
# ToDo(@all): einheiten müssen noch definiert werden
```
Meaning: Lenses: the units still have to be defined.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lens.py:20`, `nanofactorysystem/aerobasic/programs/drawings/lens.py:240`

### N060 — T34

Original:
```text
# ToDo(@all): Einheiten bestimmen
```
Meaning: Lenses: determine the units.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lens.py:24`, `nanofactorysystem/aerobasic/programs/drawings/lens.py:244`

### N061 — T34

Original:
```text
# TODO(Hannes) Implementierung von hatch size optimised mit abhängigkeit von max_height und RoC
```
Meaning: Lenses: implement a hatch size optimised with respect to max_height and radius of curvature.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lens.py:39`

### N062 — T34

Original:
```text
# TODO(dwoiwode): Müssen Kreise mit einem Radius = 0 gezeichnet werden? Oder kann dann abgebrochen werden?
```
Meaning: Lenses: must circles with radius 0 be drawn, or can the loop stop?

Locations: `nanofactorysystem/aerobasic/programs/drawings/lens.py:59`

### N063 — T34

Original:
```text
# todo save this
```
Meaning: Lenses: save this value.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lens.py:230`

### N064 — T34

Original:
```text
# ToDO einheiten
```
Meaning: Lenses: units.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lens.py:238`

### N065 — T35

Original:
```text
# todo
#   - velocity muss in mm/s sein
#   - muss übergeben werden können!
#   - kontrolle
#   - maximum speed 100*ifov size - das dann als default
#   - dynamic control of power - in the next class!
```
Meaning: IFOV_Lines: velocity must be in mm/s, must be passable and checked; the default maximum speed should be 100 × IFOV size; dynamic power control belongs to the next class.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lines.py:43`

### N066 — T35

Original:
```text
# todo change power to the corresponding value based on the calibration file - how to do it?
```
Meaning: IFOV_Lines: convert the power with the calibration file (done in T14 with PowerCalibration).

Locations: `nanofactorysystem/aerobasic/programs/drawings/lines.py:59`

### N067 — T35

Original:
```text
# todo oben hier
```
Meaning: IFOV_Lines: the speed value set here should come from the parameters above.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lines.py:85`

### N068 — T35

Original:
```text
ToDo (HR): Create Functionalities for Vector printing.
```
Meaning: Lines: create functionality for vector printing.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lines.py:193`

### N069 — T35

Original:
```text
# todo: i dont know exactly why i added Z==0 here. maybe rethink in future - 02.12 HOTFIX
```
Meaning: Rectangle3D: the author does not know why `Z == 0` was added here (hotfix of 02.12); rethink.

Locations: `nanofactorysystem/aerobasic/programs/drawings/lines.py:597`

### N070 — T35

Original:
```text
# TODO(RC) Take DropDirection into account
```
Meaning: QR code: take the DropDirection into account.

Locations: `nanofactorysystem/aerobasic/programs/drawings/qr_code.py:112`

### N071 — T36

Original:
```text
# ToDo(HR+RC) Offset in system.zline für Aerotech integrieren
```
Meaning: Z-line matrix: integrate the offset into `System.zline` for the Aerotech controller.

Locations: `nanofactorysystem/aerobasic/programs/drawings/z_line_matrix.py:23`, `nanofactorysystem/tools/focus.py:246`

### N072 — T36

Original:
```text
""" TODO: Reimplement using global variables as before so it does not have to be recompiled every time """
```
Meaning: Z-line program: reimplement with global variables, as before, so it does not have to be recompiled every time (the docstring was only this note).

Locations: `nanofactorysystem/aerobasic/programs/zline.py:6`

### N073 — T32

Original:
```text
# TODO(dwoiwode): Delete function
```
Meaning: `run_program_as_task`: the original author wanted to delete this function; it is now the central way to print layers, so rather replace than delete.

Locations: `nanofactorysystem/devices/aerotech/__init__.py:159`

### N074 — T32

Original:
```text
# todo (hr 26.2.26 - Bugfixing) here maybe deletion of prior program?
```
Meaning: `run_program_as_task`: maybe delete the previous program from the controller before loading the next one (bug fixing, 26.02.26).

Locations: `nanofactorysystem/devices/aerotech/__init__.py:174`

### N075 — T37

Original:
```text
#todo: t2-t1 seems very high - dive into code to see if there are loops which causes this or if it actually the capture time
```
Meaning: DHM: the image capture time (t2 - t1) seems very high; check for loops or whether it is really the capture time.

Locations: `nanofactorysystem/devices/dhm.py:167`

### N076 — T37

Original:
```text
# ToDo(RC) Hotfix: for oder while Schleife einbauen, minpos und maxpos prüfen, eigene Exception
```
Meaning: DHM motor scan: hotfix; implement a for/while loop, check minpos/maxpos, raise an own exception.

Locations: `nanofactorysystem/dhm/motorscan.py:352`

### N077 — T27

Original:
```text
# todo - maybe create empty file?
#   at least information about corner of experiment are important
#   as well as whole substrate drop boundaries
```
Meaning: Substrate information: maybe create an empty file; at least the experiment corners and the whole resin drop boundaries are important.

Locations: `nanofactorysystem/experiment.py:221`

### N078 — T29

Original:
```text
# + 1 todo check if +1 is necessary for planefit_mode=0
```
Meaning: Plane fitting sample points: check whether +1 is necessary for plane_fit_mode=0.

Locations: `nanofactorysystem/experiment.py:406`

### N079 — T29

Original:
```text
# ToDo(HR): Implement a controllable variable to access single plane fit outside of experiment.py
```
Meaning: Plane fitting: make single plane fits controllable outside of experiment.py.

Locations: `nanofactorysystem/experiment.py:524`

### N080 — T30

Original:
```text
# todo
#   - add structure is finished -- building program is next - how to differentiate between same name(adding (1)) and repition (adding (number repition))
#   - repition der programm funktioniert gar nicht weil in den layer programmen absolut verfahren wird und nicht relativ
```
Meaning: Structures: distinguish same names (suffix (1)) from repetitions (suffix repetition number); program repetition does not work because layer programs move absolutely, not relatively.

Locations: `nanofactorysystem/experiment.py:770`

### N081 — T33

Original:
```text
# todo doesnt work with ifov !
```
Meaning: Structure plots do not work with IFOV (commented-out code).

Locations: `nanofactorysystem/experiment.py:808`

### N082 — T29

Original:
```text
# todo check for big structures maximal deviation between corners z should be on the lowest/ highest z value depending on drop orientation
```
Meaning: For big structures, check the maximum z deviation between the corners; z should be the lowest or highest value depending on the drop direction.

Locations: `nanofactorysystem/experiment.py:821`

### N083 — T31

Original:
```text
# todo (HR) - improvement of printing process by adjustable power (between layers or even between lines)
```
Meaning: Printing: adjustable laser power between layers or even between lines.

Locations: `nanofactorysystem/experiment.py:1035`

### N084 — T37

Original:
```text
# new (HR) 23.02.2026 -> HOTFIX because wrong detection of foci - noise was detected as focus
```
Meaning: Focus detection: hotfix threshold `minDiffMax` because noise was detected as focus (values 1.7–2.5 for noise, threshold 10 chosen ad hoc).

Locations: `nanofactorysystem/tools/focus.py:416`

### N085 — T37

Original:
```text
# ToDo(HR) self.device in parameter is not existing. So this line throws an error
```
Meaning: Layer: `self.device` does not exist in Parameter, so this line throws an error.

Locations: `nanofactorysystem/tools/layer.py:119`

### N086 — T37

Original:
```text
# ToDo 2 (HR) check if there is an error or a wrong implementation of dictionary sample (dict in dict atm)
```
Meaning: Layer: check the sample dictionary (currently a dict in a dict).

Locations: `nanofactorysystem/tools/layer.py:120`

### N087 — T37

Original:
```text
# ToDo 3 (HR) Orientation MUST be "UP" or "DOWN", but it is 'Top'
```
Meaning: Layer: the orientation must be "UP" or "DOWN", but the sample says 'Top'.

Locations: `nanofactorysystem/tools/layer.py:121`

### N088 — T37

Original:
```text
# TODO(RC): Merge with Dominik's result object
```
Meaning: Layer: merge the result with Dominik's result object.

Locations: `nanofactorysystem/tools/layer.py:145`

### N089 — T37

Original:
```text
# ToDo (HR) Hotfix beseitigen! Orientation in dieser Datei ändern und in Scanner ändern und abhängig von DropDirection machen. dazu dropdirection ins system dict rein
```
Meaning: Layer: remove the hotfix; change the orientation here and in Scanner to depend on DropDirection, and put the drop direction into the system dictionary.

Locations: `nanofactorysystem/tools/layer.py:211`

### N090 — T37

Original:
```text
# TODO: With modulo slightly different edge cases (-180 vs 180)
```
Meaning: Plane: normalising the angle with modulo gives slightly different edge cases (-180 vs 180).

Locations: `nanofactorysystem/tools/plane.py:62`

### N091 — T38

Original:
```text
# TODO: Laser power auslesen
```
Meaning: Visualization: read the laser power from the program.

Locations: `nanofactorysystem/utils/visualization.py:150`

### N092 — T38

Original:
```text
# TODO: Laser power als Farbe
```
Meaning: Visualization: show the laser power as colour.

Locations: `nanofactorysystem/utils/visualization.py:268`, `nanofactorysystem/utils/visualization.py:317`

### N093 — T38

Original:
```text
# TODO: Does not work
```
Meaning: Visualization: disabling scientific notation of the axis labels does not work.

Locations: `nanofactorysystem/utils/visualization.py:290`, `nanofactorysystem/utils/visualization.py:360`

### N094 — T39

Original:
```text
ToDo: To be done and implemented!
```
Meaning: Manual DHM helper: the reset method is not implemented.

Locations: `test/manual/dhm/DHMUserBackend.py:73`

### N095 — T40

Original (`nanofactorysystem/aerobasic/slicer/TODO.txt`, file deleted):
```text
Roadmap Points:

abgeschlossen; 

(1) Toolpath-IR und `units.py`
(2) Preprocessor
(4) Storage v2
(7) Pfadoptimierer

offen: 
(3) Kontur-als-Polylinie 
(5) gekipptes Slicing
(6) Shell-Strategie 
(8) Experiment-Hierarchie
(9) Studien-Framework
(10) Übersetzer
```
Meaning: roadmap of the slicer port (tpp_slicer). Done: (1) toolpath IR and `units.py`, (2) preprocessor,
(4) storage v2, (7) path optimiser. Open: (3) contour as polyline, (5) tilted slicing, (6) shell strategy,
(8) experiment hierarchy, (9) study framework, (10) translator.

## Work packages

In the style of `TODO.md`. IDs continue the numbering of `TODO.md`; move a package there to schedule it.

- [ ] T26: Parameterise the experiment scripts instead of copying them (from T19)
      Goal: Experiment parameters are passed to one parameterised print function instead of being edited in ~45 copied scripts.
      Priority: medium | Depends on: –
      Done when:
        - The print function of the template accepts `sys_args`, drop direction, grid, `n_mid_points`, structure size and FOV as parameters (N001, N002, N006–N008, N013).
        - Hardcoded values such as the DHM-paper value (N021) are determined automatically or passed in.
        - The copied scripts in `mains/Experiments/` use the parameterised function, or are marked as historical.

- [ ] T27: Organise experiment data per substrate (from T19)
      Goal: Several experiments on one substrate are stored without overwriting and can be found again.
      Priority: medium | Depends on: –
      Done when:
        - The output folder allows several prints of one experiment on one substrate without deleting earlier data, with a sensible default location (N003–N005).
        - Substrates are identified, and substrate information is always stored, including the experiment corners and the resin drop boundaries (N011, N024, N077).
        - An experiment index/database by substrate, date and objective exists (N025).

- [ ] T28: Overview images and time estimate (from T19)
      Goal: An experiment documents the whole scene and its expected duration.
      Priority: low | Depends on: –
      Done when:
        - An overview image of the whole scene is taken before and after printing (N009).
        - The expected and the actual duration of an experiment are logged (N023).

- [ ] T29: Improve plane fitting and position checks (from T19)
      Goal: Plane fitting is controllable and positions are validated.
      Priority: medium | Depends on: –
      Done when:
        - A "border only" plane-fit mode exists, and single plane fits can be run outside `experiment.py` (N026, N079).
        - The `+1` in the sample points for `plane_fit_mode=0` is checked (N078).
        - The experiment center is validated against the resin drop edges (N022).
        - For big structures, the z deviation between the corners is checked (N082).

- [ ] T30: Make restarts and repetitions robust (from T19)
      Goal: An aborted experiment can be resumed repeatedly at the right layer and keeps its identity.
      Priority: medium | Depends on: –
      Done when:
        - A restarted experiment keeps its UUID/QR text (N027).
        - Resuming after a second abort starts at the right layer; a dummy-backend test covers two aborts (N028).
        - Structure names and repetitions are distinguished, and repetitions work although layer programs move absolutely (N080).

- [ ] T31: Adjustable laser power during printing (from T19)
      Goal: The laser power can change between structures, layers or lines.
      Priority: medium | Depends on: –
      Done when:
        - Parameter test prints can change the power between structures (N012).
        - `print_structure` supports a power per layer, or per line where the programs allow it (N083).

- [ ] T32: Clean up the AeroBasic API and task handling (from T19)
      Goal: The AeroBasic API is correct and complete for the commands in use.
      Priority: medium | Depends on: –
      Done when:
        - `PROGRAM_ASSOCIATE` sends the correct syntax (N029); reading system parameters is possible (N030).
        - Program text: compact variable declarations, header metadata, and a mode check for VELOCITY/ABSOLUTE (N031–N033).
        - IFOV setup: ramp types and the F threshold are investigated and documented (N044, N045).
        - `run_program_as_task`: better task-id choice, cleanup of the previous program, and a decision on the old "delete this function" note (N058, N073, N074).

- [ ] T33: Review the grating, DOE and height-function structures (from T19)
      Goal: Grating-type structures are correctly parameterised and stitched.
      Priority: medium | Depends on: –
      Done when:
        - The DOE algorithm is documented or implemented (N034); the grating orientation axis is a parameter; the width parameterisation is decided; `full_width` is respected (N035–N037).
        - Gratings use the stitcher and tile boundaries; the unexplained todos are resolved (N047–N050).
        - Height-function structures: Cohen-Sutherland clipping, aperture for the base, task number per tile; the unexplained note is resolved (N051–N054).
        - IFOV gratings: polyline-based hatching variant, the questioned step, and the LINEAR-outside-IFOV influence are checked (N055–N057); structure plots work with IFOV (N081).

- [ ] T34: Finish the lens and stacked-lens structures (from T19)
      Goal: Lens structures have defined units and a finished stacked-lens implementation.
      Priority: medium | Depends on: –
      Done when:
        - Units of the lens classes are defined and documented (N059, N060, N064).
        - Hatch size optimised for max height and radius of curvature; zero-radius circles handled; the value to be saved is stored (N061–N063).
        - Stacked lens: z values, spacing, Rectangle3D x/y meaning, connection without overlap and the layer calculation are fixed, and the unfinished part is completed (N038–N043).

- [ ] T35: Clarify line, rectangle and QR-code details (from T19)
      Goal: Line-based structures have checked parameters and no unexplained hotfixes.
      Priority: low | Depends on: –
      Done when:
        - `IFOV_Lines`: velocity unit (mm/s), validation, default maximum speed (100 × IFOV size) and the speed values from parameters (N065–N067).
        - Vector printing functionality is designed (N068).
        - The `Z == 0` hotfix in `Rectangle3D` is understood and replaced or documented (N069).
        - `QRCode` takes the DropDirection into account (N070).

- [ ] T36: Z-line: offset, global variables and focal-point script (from T19)
      Goal: Z-line programs are consistent and the focal-point study script is complete.
      Priority: low | Depends on: –
      Done when:
        - The camera offset is integrated into `System.zline` (N071); the z-line program uses global variables and is not recompiled every time (N072).
        - `z_line_focal_points.py`: dz split, z recalculation, noise on dz, min_distance, boundary, result dictionary and file-exists check are resolved (N014–N020).

- [ ] T37: Replace the hotfixes in tools and devices (from T19)
      Goal: Focus, layer, plane, DHM and serialization code have no open hotfixes.
      Priority: medium | Depends on: –
      Done when:
        - The focus-detection noise threshold `minDiffMax` is replaced by a justified criterion, and its value is checked for 63x (N084, N010).
        - Layer: sample dictionary, orientation (UP/DOWN from DropDirection), missing `self.device`, and the result object are fixed (N085–N089).
        - The plane angle edge case (-180 vs 180) is handled (N090).
        - DHM: capture time analysed; motor scan loop with limit checks and an own exception (N075, N076).
        - `DrawableObject._init_args` stores "data" instead of the hotfix (N046).

- [ ] T38: Visualization: laser power and axis formatting (from T19)
      Goal: Movement plots show the laser power and readable axes.
      Priority: low | Depends on: –
      Done when:
        - The laser power is read from the program and shown as colour (N091, N092).
        - Axis labels are shown without scientific notation (N093).

- [ ] T39: Manual DHM helper: implement reset (from T19)
      Goal: The interactive DHM helper can reset its state.
      Priority: low | Depends on: –
      Done when:
        - `test/manual/dhm/DHMUserBackend.py` implements its reset method (N094).

- [ ] T40: Slicer roadmap: open items (from T19)
      Goal: The open items of the slicer roadmap are planned or done.
      Priority: low | Depends on: –
      Done when:
        - Contour as polyline, tilted slicing, shell strategy, experiment hierarchy, study framework and translator are implemented or explicitly dropped (N095).



## Notes of Claude Code 

Where I deviated or you should check
T25: my original finding (a logger path being passed as a logger) was wrong. The real problem was the placeholder values; the log entry says so.
T18: I translated the package and test modules only. The experiment scripts in mains/ and the scripts in test/manual/ still contain German.
Safety: with --run-hardware, test_move_home moves the real stage to X=Y=Z=0, as it did before. Please check whether Z=0 is safe with the objective mounted.
Logger name: the logger is still called 'dummy'; renaming it is your call.