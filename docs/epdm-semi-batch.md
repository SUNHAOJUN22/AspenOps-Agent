# EPDM Semi-batch Modeling Boundary

A semi-batch EPDM experiment in which catalyst and ENB are charged initially while ethylene and propylene continue to feed is dynamic.

Representative balances include:

\[
\frac{dn_E}{dt}=F_E-r_E V,
\qquad
\frac{dn_P}{dt}=F_P-r_P V
\]

\[
\frac{dn_{ENB}}{dt}=-r_{ENB}V
\]

\[
\frac{da}{dt}=-k_d(T,C)a
\]

\[
\rho C_pV\frac{dT}{dt}=\dot Q_{rxn}+\dot Q_{feed}-UA(T-T_j)
\]

Molecular-weight and composition distributions may require moment equations or a population-balance model.

## What v1.0 can do

- automate steady-state or quasi-steady Aspen Plus cases;
- evaluate thermodynamic states and auxiliary flowsheets at selected conditions;
- run parameter sweeps, continuation and outer-loop optimization;
- enforce units, ranges and convergence evidence.

## What v1.0 must not claim

A single Aspen Plus steady-state solve is not the complete semi-batch trajectory. It cannot by itself reproduce initial-only catalyst/ENB charge, catalyst deactivation, changing liquid volume and time-dependent monomer uptake.

## Valid implementation paths

1. external Python ODE/PBE integrator calls Aspen for property or flowsheet evaluations;
2. Aspen Custom Modeler implements the dynamic equations;
3. Aspen Dynamics represents a qualified dynamic flowsheet;
4. controlled quasi-steady time slices are used with an explicit approximation and validation study.

A future adapter should be a separate backend with its own state model and integration tests, not a hidden extension of the steady-state COM backend.
