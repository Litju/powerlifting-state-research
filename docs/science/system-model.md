# Scientific system model

The benchmark program treats athlete performance as a synthetic dynamical-system problem. It distinguishes latent capacity from observed performance and from temporary expression of performance. These are different scientific quantities.

Training exposure and planned interventions are system inputs. Population construction describes variation in starting conditions and athlete-specific parameters. An observation model maps the latent or expressed system to recorded measurements, including its uncertainty and availability. A task then fixes what is forecast, when the forecast is made, which inputs are visible, and how predictions are evaluated.

The abstraction supports prediction studies inside declared synthetic systems. Predictive accuracy does not by itself identify latent coordinates or parameters, establish causal effects, or validate the system against real athletes. Each benchmark record states its own target and information setting.

This document states semantic separations. It does not specify or implement the mechanics of any historical world.

## Executable public capacity/expression law

For one lift, daily dose $d_t\geq0$ and intensity $i_t\geq0$ produce bounded stimulus

$$s_t=\frac{d_ti_t}{d_ti_t+s_{ref}},\qquad s_{ref}=0.6\frac{1-r_{ref}}{r_{ref}}.$$

Starting from $A_{-1}=S_{-1}=0$, the public simulator evolves

$$A_t=\alpha_A A_{t-1}+(1-\alpha_A)s_t,\quad C_t=B(1+g_AA_t),$$
$$S_t=\alpha_S S_{t-1}+(1-\alpha_S)s_t,\quad E_t=C_t(1-g_SS_t),\quad
\alpha_A=e^{-1/\tau_A},\ \alpha_S=e^{-1/\tau_S}.$$

$C_t$ is capacity and $E_t$ is expressed performance. The simulator has no cross-lift dynamical edge or process disturbance. These are synthetic assumptions, not an empirically identified fitness–fatigue law. The [implemented dynamics](../../src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/dynamics.py) and [population mapping](../../src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/population.py) are authoritative for the public world.

At days 6,13,…,223, assessment is $E_t(1+\epsilon)$ with Gaussian coefficient of variation 0.05/0.04/0.05 for squat/bench/deadlift. Prescribed load $L_t$ is a uniform 0.68–0.71 fraction of that noisy assessment. The generator uses true relative load $q_t=L_t/E_t$ to produce expected velocity $v_0+b((1-q_t)/0.60)^p$, with lift-specific constants and additive Gaussian noise of standard deviation 0.04/0.03/0.05 m/s. The valid generator domain is $q_t\in[0.40,1.00]$; invalid/nonfinite observations are rejected, not clipped. See [observation source](../../src/powerlifting_state_research/benchmarks/latent_capacity_change_with_transient_expression_forecasting/observations.py).

The predictor sees $L_t$/noisy assessment, not $L_t/E_t$. That distinction prevents latent expression leakage. Target $C_{t_0+h-1}-C_{t_0-1}$ uses $t_0=224$ and $h\in\{14,28,56\}$. With zero future dose, adaptation decays, implying nonpositive target capacity change. This is the exact synthetic support rule used by [cessation truncation](../studies/probabilistic-capacity-forecasting.md); other plans have no universal sign restriction.

The [research positioning](research-positioning.md) connects these components to the literature and distinguishes simulation, mechanistic baselines, data-driven learning and inference-time support constraints.
