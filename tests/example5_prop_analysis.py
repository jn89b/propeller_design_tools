import propeller_design_tools as pdt
import matplotlib.pyplot as plt


# no need to set the foil or propeller directories if already set from previously run scripts

# load up the previously created propeller
prop = pdt.Propeller('MyPropeller')
# prop.plot_design_point_panel()    # plot design point for reference if needed
# prop.clear_sweep_data()           # clear existing sweep data if desired

# set key-word arguments for the sweep command
sweep_kwargs = {
    'velo_vals': [9, 12, 15, 18, 21],       # speed, m/s
    'sweep_param': 'thrust',                # must be one of 'adva', 'rpm', 'thrust', 'power', 'torque'
    'sweep_vals': [5, 10, 15, 20, 25, 30],
    'verbose': True,                        # print what PDT is doing?
    'xrotor_verbose': False,                # print XROTOR's raw output?
    'vorform': 'pot'                        # 'pot', 'grad', or 'vrtx'
}

# actually run the sweep
# prop.analyze_sweep(**sweep_kwargs)

# use the propeller's "oper_data" attribute, which has a plot() method, to access and plot the data
figure = prop.oper_data.plot(x_param='rpm', y_param='Efficiency', family_param='speed', iso_param='thrust')
plt.savefig('another_test.png')

# below are valid options for x_param, y_param, family_param, and iso_param
# 'adv. ratio', 'J', 'speed(m/s)', 'rpm', 'thrust(N)', 'power(W)', 'torque(N-m)', 'Efficiency',
# 'Eff induced', 'Eff ideal', 'Pvisc(W)', 'Ct', 'Tc', 'Cp', 'Pc', 'Sigma'


