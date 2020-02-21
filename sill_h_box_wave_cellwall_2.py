#!/usr/bin/env python
# encoding: utf-8

r"""
Shallow water flow with zero-width barrier slightly off grid edge by alpha*dx
======================================================================
Solve the one-dimensional shallow water equations including bathymetry:
.. math::
    h_t + (hu)_x & = 0 \\
    (hu)_t + (hu^2 + \frac{1}{2}gh^2)_x & = -g h b_x.
Here h is the depth, u is the velocity, g is the gravitational constant, and b
the bathymetry.
"""
import sys
import numpy
import matplotlib.pyplot as plt
from clawpack import riemann
import shallow_1D_redistribute_wave_MB_2
from clawpack.pyclaw.plot import plot

def before_step(solver, states):
    drytol = states.problem_data['dry_tolerance']
    for i in range(len(states.q[0,:])):
        states.q[0,i] = max(states.q[0,i], 0.0)
        if states.q[0,i] < drytol:
            states.q[1,i] = 0.0
    return states

def load_parameters(fileName):
    fileObj = open(fileName)
    params = {}
    for line in fileObj:
        line = line.strip()
        key_value = line.split('=')
        params[key_value[0]] = key_value[1]
    return params

def steady_bc(state,dim,t,qbc,auxbc,num_ghost=2):
    qbc[0,1] = qbc[0,2]
    qbc[1,1] = 0.4
    qbc[:,0] = qbc[:,1]

    qbc[:,-2] = qbc[:,-3]
    qbc[:,-1] = qbc[:,-2]

    auxbc[0,1] = auxbc[0,2]
    auxbc[0,0] = auxbc[0,1]
    auxbc[0,-2] = auxbc[0,-3]
    auxbc[0,-1] = auxbc[0,-2]
def setup(kernel_language='Python',use_petsc=False, outdir='./_output_cellwall_3_2_wet', solver_type='classic'):

    if use_petsc:
        import clawpack.petclaw as pyclaw
    else:
        from clawpack import pyclaw

    params = load_parameters('parameters_h_box_wave.txt')
    xlower = float(params['xlower'])
    xupper = float(params['xupper'])
    cells_number = int(params['cells_number'])
    nw = int(params['wall_position']) # index of the edge used to present the wall
    alpha = float(params['fraction'])
    wall_height = float(params['wall_height'])

    x = pyclaw.Dimension(xlower, xupper, cells_number, name='x')
    domain = pyclaw.Domain(x)
    state = pyclaw.State(domain, 2, 2)
    xc = state.grid.x.centers

    # Gravitational constant
    state.problem_data['grav'] = 9.8
    state.problem_data['sea_level'] = 0.0

    # Wall position
    state.problem_data['wall_position'] = nw
    state.problem_data['wall_height'] = 0#wall_height
    state.problem_data['fraction'] = alpha
    state.problem_data['dry_tolerance'] = 0.001
    state.problem_data['max_iteration'] = 1
    #state.problem_data['method'] = 'h_box_wave' # shifting the grid makes this unnecessary!
    state.problem_data['zero_width'] = True
    #state.problem_data['arrival_state'] = False # shifting the grid makes this unnecessary!
    state.problem_data['xupper'] = xupper
    state.problem_data['xlower'] = xlower
    state.problem_data['cells_num'] = cells_number


    solver = pyclaw.ClawSolver1D(shallow_1D_redistribute_wave_MB_2.shallow_fwave_hbox_dry_1d)

    solver.limiters = pyclaw.limiters.tvd.minmod
    solver.order = 1
    solver.cfl_max = 0.8
    solver.cfl_desired = 0.7
    solver.kernel_language = "Python"
    solver.fwave = True
    solver.num_waves = 3
    solver.num_eqn = 2
    solver.before_step = before_step
    solver.bc_lower[0] = pyclaw.BC.custom
    solver.user_bc_lower = steady_bc
    solver.bc_upper[0] = pyclaw.BC.custom
    solver.user_bc_upper = steady_bc
    solver.aux_bc_lower[0] = pyclaw.BC.extrap
    solver.aux_bc_upper[0] = pyclaw.BC.extrap

    # Initial Conditions
    xpxc = (cells_number) * 1.0 / (cells_number-1)
    state.problem_data['xpxc'] = xpxc
    state.aux[0, :] = - 1.2 * numpy.ones(xc.shape)

    ## slope bathymetry
    # bathymetry = numpy.linspace(-0.8, -0.4, xc.shape[0] - 1, endpoint=True)
    # state.aux[0,:nw-1] = bathymetry[:nw-1]
    # state.aux[0,nw-1] = bathymetry[nw-1]
    # state.aux[0,nw:] = bathymetry[nw-1:]
    # state.aux[0, :] = numpy.linspace(-0.8, -0.4, xc.shape[0], endpoint=True)
    # state.aux[0,nw+1:] = -0.6
    state.aux[0,nw] = -0.3

    #state.aux[1,:] = numpy.zeros(xc.shape)
    #state.aux[1, :] = xpxc # change this to actual delta x_p and xp is actuallly 1/N-1
    # shifting the grid such that barrier aligns with cell edge nw and pushing the small cells to the endpoint boundaries
    # so will need two hbox pairs: one at left endpoint and one at right endpoint
    #state.aux[1, nw-1] = alpha * xpxc
    #state.aux[1, nw] = (1 - alpha) * xpxc
    state.q[0, :] = -0.0 - state.aux[0, :]
    # state.q[0, nw:] = 0 # uncomment for dry state on right side of wall
    # state.q[0,:80] += 0.5
    # state.q[0,nw+1:] = 0
    # state.q[0,nw+1:] = 0.3
    state.q[0,:] = state.q[0,:].clip(min=0)
    state.q[1,:nw] = 0.4
    state.q[1,nw:] = 0.5


    claw = pyclaw.Controller()
    claw.keep_copy = True
    claw.tfinal = 1.4
    claw.solution = pyclaw.Solution(state, domain)
    claw.solver = solver
    # claw.setplot = setplot
    claw.write_aux_init = True

    dx = claw.solution.domain.grid.delta[0]

    state.mF=1
    init_mass = print(numpy.sum(state.q[0,:]*(1/cells_number)*state.aux[1,:],axis=0))
    def mass_change(state):
        #print(state.q[0,:])
        state.F[0,:] = numpy.sum(state.q[0,:]*(1/cells_number)*state.aux[1,:],axis=0)
    claw.compute_F = mass_change
    claw.F_file_name = 'total_mass'


    claw.output_style = 1
    claw.num_output_times = 20
    claw.nstepout = 1

    # if outdir is not None:
    #     claw.outdir = outdir
    # else:
    #     claw.output_format = None

    claw.outdir = outdir
    if outdir is None:
        claw.output_format = None

    claw.run()
#    return claw

    # check conservation:
# get the solution q and capacity array and give out the mass
    print("change in water vol",((numpy.sum(claw.frames[0].q[0,:]*(1/cells_number)*state.aux[1,:],axis=0))  - (numpy.sum(claw.frames[-1].q[0,:]*(1/cells_number)*state.aux[1,:],axis=0)))/numpy.sum(claw.frames[0].q[0,:]*(1/cells_number)*state.aux[1,:],axis=0))
    plot_kargs = {'problem_data':state.problem_data}
    plot(setplot="./setplot_h_box_wave.py",outdir='./_output_cellwall_3_2_wet',plotdir='./plots_actual_3_2_wet_p',iplot=False, htmlplot=True, **plot_kargs)

#setplot="./setplot_h_box_wave.py"

if __name__=="__main__":
#    from clawpack.pyclaw.util import run_app_from_main
#    setplot="./setplot_h_box_wave.py"
#    output = run_app_from_main(setup,setplot)
    setup()
