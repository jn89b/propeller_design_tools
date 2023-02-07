import propeller_design_tools as pdt
import numpy as np


pdt.start_ui()

# prop = pdt.Propeller('MyPropeller')

# prop = pdt.Propeller('first_try_clarky')
# prop.show_station_fits()

# sweep_kwargs = {
#     'velo_vals': np.arange(.1, 1, 0.1),
#     'sweep_param': 'thrust',
#     'sweep_vals': np.arange(600, 2400, 150)
# }

# prop.clear_sweep_data()
# prop.analyze_sweep(**sweep_kwargs)
# prop.oper_data.plot(x_param='J', y_param='thrust(N)', family_param='speed(m/s)', iso_param='power(W)')

# pdt.create_propeller(
#     name='first_try_clarky',
#     nblades=3,
#     radius=1,
#     hub_radius=0.12,
#     hub_wake_disp_br=0.12,
#     design_speed_mps=.2,
#     design_adv=.05,
#     design_rpm=None,
#     design_thrust=750,
#     design_power=None,
#     design_cl={'const': 0.5},
#     design_atmo_props={'altitude_km': -1},
#     design_vorform='vrtx',
#     station_params={0.75: 'clarky'},
#     geo_params={'tot_skew': 45, 'n_prof_pts': None, 'n_profs': 50},
#     )
