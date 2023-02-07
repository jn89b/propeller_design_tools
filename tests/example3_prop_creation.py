import propeller_design_tools as pdt


pdt.set_airfoil_database(r"C:\Users\jnguy\Documents\School\PHD Spring 2023\acs_class\propeller_design_tools\propeller_design_tools\foil_database")
pdt.set_propeller_database(r"C:\Users\jnguy\Documents\School\PHD Spring 2023\acs_class\propeller_design_tools\propeller_design_tools\prop_database")

prop = pdt.create_propeller(    # ALL UNITS IN BASE SI UNLESS OTHERWISE SPECIFIED
    name='MyPropeller',         # pick a name
    nblades=3,                  # number of blades
    radius=0.18,                 # tip radius from center of hub
    hub_radius=0.03,            # how big the hub?
    hub_wake_disp_br=0.03,      # how big the "hub-wake-displacement-body-radius" ... As far as I can find ...
    design_speed_mps=25,            # how fast you wanna go, normally
    design_cl={'const': 0.5},  # valid: either 'const' or BOTH 'root' & 'tip' (also 'file' maybe, you try it)
    design_atmo_props={'altitude_km': 5},  # valid: 'altitude_km', 'vsou', 'dens', 'visc' (altitude_km=-1 is underwater)
    design_vorform='grad',      # valid: either 'grad', 'pot', or 'vrtx' (type of solver for XROTOR to use)
    design_rpm=5500,            # target rotations per minute of the design (only give 1 of rpm/adv)
    # design_adv=0.2,              # target advance ratio of the design - XROTOR "adv" definition (only give 1 of rpm/adv)
    # design_power=400,           # target power of the design (only give 1 of power/thrust)
    design_thrust= 20,           # target thrust of the design (only give 1 of power/thrust)
    n_radial=50,                # number of radial vortices for XROTOR to use in its calculations
    station_params={0.75: 'clarky'},    # Desired (normalized) radial station locations - only 1 currently supported
    geo_params={'tot_skew': 15, 'n_prof_pts': None, 'n_profs': 50},  # extra PDT options to use in 3D geometry creation
)
