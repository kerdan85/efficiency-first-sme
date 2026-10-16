"""Text blocks for the urbs energy-system optimisation (inserted by scripts/build_processes_manuscript.py)."""

PROBLEM4 = r"""

\emph{Problem D, joint cost-optimal design.} The fourth problem removes the sequencing assumption altogether. A linear programme built in the open energy-system optimisation model urbs (Section~\ref{sec:urbsmethod}) chooses simultaneously how much of each efficiency measure to adopt, the PV and battery capacities and the hourly operation of the plant's electricity system, with and without caps on grid emissions. Because it is solved independently of Problems A--C, it tests whether efficiency first emerges from cost minimisation rather than being imposed, and it extends the analysis to deep decarbonisation, where storage becomes necessary."""

METHODS = r"""\subsection{Joint cost-optimal design with urbs}
\label{sec:urbsmethod}
urbs is an open-source linear optimisation model for distributed energy systems developed at the Technical University of Munich~\cite{urbs}. It represents an energy system as commodities linked by processes and storage, and minimises the annualised cost of meeting an hourly demand. Here the plant is modelled as one site with one electricity bus over one year of 8,760 hours (Figure~\ref{fig:urbsstructure}). Grid purchases, rooftop PV, the battery and the four energy-saving measures supply the bus. The plant demand, exports and curtailment draw from it. The hourly load and PV output are those of Section~\ref{sec:nzmethod}.

\begin{figure}[H]
\begin{adjustwidth}{-\extralength}{0cm}
\centering
\includegraphics[width=\linewidth]{figures/fig_urbs_structure.pdf}
\end{adjustwidth}
\caption{Structure of the urbs model of the plant.}
\label{fig:urbsstructure}
\end{figure}

The efficiency measures enter as ``negawatt'' processes. Let $\hat{s}_{m,t}$ be the hourly saving of measure $m \in \mathcal{M}=\{\mathrm{E1},\ldots,\mathrm{E4}\}$ at full implementation, taken from the hourly model, and $a_m \in [0,1]$ the adopted fraction. The avoided kWh $a_m\hat{s}_{m,t}$ are supplied to the bus at the measure's investment cost, O\&M and lifetime, so that a measure competes with PV and storage as a resource, as the EE1st principle requires. With PV capacity $k$ (kWp) and hourly yield $y_t$ (kWh~kWp$^{-1}$), usable battery capacity $b$ (kWh, 90\% of nameplate), grid imports $g_t$, exports $x_t$, curtailment $c_t$, battery charge $q^{+}_t$, discharge $q^{-}_t$ and state of charge $e_t$, the programme is
\begin{align}
\min\quad & \sum_{m\in\mathcal{M}} a_m\left(\alpha_m I_m + F_m\right) + k\left(\alpha_{\mathrm{PV}} I_{\mathrm{PV}} + F_{\mathrm{PV}}\right) + b\left(\alpha_{\mathrm{B}} I_{\mathrm{B}} + F_{\mathrm{B}}\right) + \sum_{t=1}^{8760}\left(v\,g_t - p_x\,x_t\right) \label{eq:urbsobj}\\
\text{s.t.}\quad & g_t + k\,y_t + \sum_{m} a_m \hat{s}_{m,t} + q^{-}_t = d_t + x_t + c_t + q^{+}_t \qquad \forall t \label{eq:urbsbal}\\
& e_t = e_{t-1} + \eta\,q^{+}_t - q^{-}_t/\eta, \qquad 0 \le e_t \le b, \qquad q^{+}_t,\,q^{-}_t \le \rho\,b/\delta \qquad \forall t \label{eq:urbssto}\\
& 0 \le k \le \bar{k}, \qquad 0 \le a_m \le 1 \label{eq:urbscap}\\
& \textstyle\sum_t x_t \le \sum_t g_t \quad \text{(net metering only)} \label{eq:urbsnm}\\
& \varepsilon \textstyle\sum_t g_t \le \phi\,\varepsilon \sum_t d_t \quad \text{(emission cap)}, \label{eq:urbsco2}
\end{align}
where $d_t$ is the hourly demand without measures, $I$ and $F$ are investment and fixed O\&M costs (for the battery per usable kWh, i.e., the nameplate cost divided by $\delta$), $\alpha$ is the capital recovery factor at the 10\% discount rate over each asset's lifetime, $\eta=\sqrt{0.85}$ is the one-way battery efficiency, $\rho$ the power-to-energy ratio (0.5~kW per kWh of nameplate capacity), $\delta=0.9$ the usable fraction of nameplate capacity, $\varepsilon$ the grid emission factor and $\phi$ the cap as a fraction of baseline emissions. The battery starts and ends the year half full.

Grid purchases are priced at the marginal value $v$ of Equation~(\ref{eq:marginal}); this is appropriate because GDMTO demand charges are proportional to energy, whereas the fixed charges and the power-factor adjustment do not depend on the decisions optimised, which is also why power-factor correction (E5) is excluded. The PV investment cost includes the inverter replacement, and the array is limited to $\bar{k}=700$~kWp, the 0.7~MW distributed-generation limit applied conservatively to DC capacity. Arrays above about 164~kWp exceed the roof area documented in the audit (Section~\ref{sec:nzresults}) and would require additional roof or ground area; the roof-limited scenario bounds this case. Battery capacities from urbs are reported as usable kWh, whereas those of the hourly design search refer to nameplate kWh. The savings of base-load control are assigned to the hours in which it reduces load, preserving its monthly energy. Three compensation regimes, which differ from those of the hourly design search, set the export price $p_x$: annual net metering, in which exports are credited at $v$ subject to Equation~(\ref{eq:urbsnm}); net billing, in which exports are paid 1.0~\MXN~kWh$^{-1}$; and self-consumption, in which exports have no value. Surplus PV output can be curtailed. Penalties of $10^{-3}$~\MXN~kWh$^{-1}$ on exports and battery throughput remove degenerate solutions with simultaneous import and export or simultaneous charge and discharge; they do not affect the results.

\begin{table}[H]
\caption{Scenarios solved with urbs.}
\label{tab:urbsruns}
\footnotesize
\begin{tabularx}{\linewidth}{p{3.2cm}Xr}
\toprule
Scenario set & Settings & Runs \\
\midrule
Compensation regimes & Net metering, net billing, self-consumption; no emission cap & 6 \\
Roof limit & Net metering; $\bar{k}=163.8$~kWp (audit layout) & 2 \\
Emission caps & Net metering; $\phi$ = 35, 30, 25, 20, 15, 10\% & 12 \\
Battery cost & Net metering; battery cost 75, 50, 25\% of central; no cap and $\phi$ = 20\% & 12 \\
\bottomrule
\end{tabularx}
\end{table}

Each scenario is solved twice, with the measures available ($a_m \in [0,1]$) and without them ($a_m = 0$, supply only), which isolates the contribution of efficiency at every point (Table~\ref{tab:urbsruns}). The \nUNRuns\ linear programmes, each with 8,760 hourly time steps, were solved with HiGHS through Pyomo in about \nUSolveMean~s each.

"""

RESULTS = r"""\subsection{Joint cost-optimal design with urbs}
\label{sec:urbsresults}

\subsubsection{Cost-optimal designs under three compensation regimes}
Without an emission cap and under annual net metering, the cost-optimal supply-only design is a \nUPVNMS~kWp array without storage (Table~\ref{tab:urbs}). This is the annual net-zero size found by the hourly design search in Section~\ref{sec:nzresults}, with the same hourly self-sufficiency of \nUSSNMS\%, so the two models describe the same system. When efficiency is available, the optimiser adopts base-load control and insulation in full but not the servo motors or the compressed-air package. It installs \nUPVNME~kWp of PV and lowers the annualised cost from \nUCostNMS\ to \nUCostNME~k\MXN\ (\nUCostNMSave\%). This choice follows the merit order of Section~\ref{sec:cceresults}. Under annual net metering every kWh of PV output is worth the full tariff, so a measure enters only if its CCE is below the PV LCOE, and E2 and E1 lie just above it.

As soon as PV output loses part of its value, all four measures enter the optimum. With PV limited to the 163.8~kWp array, without export compensation, or with net billing at 1.0~\MXN~kWh$^{-1}$, efficiency lowers the annualised cost by \nUCostRLSave\%, \nUCostSCSave\% and \nUCostNBSave\%, respectively. Under net billing the export price exceeds the PV LCOE, so the array grows to the 0.7~MW limit with or without efficiency. The similar PV sizes and imports of the self-consumption and roof-limited designs with efficiency are a coincidence of the two constraints. In no regime are batteries part of the cost-optimal design without an emission cap.

\input{tables/urbs.tex}

\subsubsection{Decarbonisation frontier and order of adoption}
Caps on gross grid emissions trace the cost-optimal decarbonisation frontier (Figure~\ref{fig:urbs}). The unconstrained optima already reduce gross grid CO$_2$ to \nUCOONME\% of the baseline with efficiency and \nUCOONMS\% without it. As the cap tightens, the optimiser adopts resources in a clear order (Figure~\ref{fig:urbs}c). It first completes the efficiency bundle: at a 35\% cap the servo motors are adopted at \nUEtwoAdoptThirtyFive\%, and all measures are adopted from 30\% onwards. Storage is added next, with the array re-optimised slightly downwards, and PV grows beyond its unconstrained optimum only at caps of 20\% or less. Batteries enter at a cap of \nUFirstBatS\% without efficiency but only at \nUFirstBatE\% with it. At a 20\% cap the efficiency-first optimum needs \nUPVTwentyE~kWp of PV and \nUBatTwentyE~kWh of storage instead of \nUPVTwentyS~kWp and \nUBatTwentyS~kWh. At 10\% it needs \nUPVTenE~kWp and \nUBatTenE~kWh instead of \nUPVTenS~kWp and \nUBatTenS~kWh.

The cost of the frontier rises steeply once storage is required (Figure~\ref{fig:urbs}a). With efficiency, the annualised cost is \nUCostThirtyE~k\MXN\ at a 30\% cap and \nUCostTwentyE~k\MXN\ at 20\%, against \nUCostThirtyS\ and \nUCostTwentyS~k\MXN\ without it. Across the caps examined, efficiency lowers the annualised cost of meeting the cap by \nUCapSaveMin--\nUCapSaveMax\%. At a 10\% cap the annualised cost is \nUCostTenE~M\MXN\ with efficiency and \nUCostTenS~M\MXN\ without, both above the \nUGridCost~k\MXN\ per year of buying all electricity from the grid. Net grid purchases are close to zero along the frontier, because annual exports offset imports under net metering. Storage then accounts for \nUBatShareTenE\% of the annualised cost with efficiency and \nUBatShareTenS\% without it, whereas the measures account for only \nUEEShareTenE\% (Figure~\ref{fig:urbs}d).

\begin{figure}[H]
\begin{adjustwidth}{-\extralength}{0cm}
\centering
\includegraphics[width=\linewidth]{figures/fig9_urbs.pdf}
\end{adjustwidth}
\caption{Cost-optimal decarbonisation frontier from urbs (net metering): (a) annualised cost; (b) PV and battery capacity; (c) adoption of each measure; (d) annualised cost by component.}
\label{fig:urbs}
\end{figure}

\subsubsection{Hourly operation}
Figure~\ref{fig:urbsdispatch} shows how the two optimal systems for a 20\% cap operate in a dry-season week and in a week of the 24-hour shift months. The negawatts of the measures lower the load in every hour, including the nights and weekends that PV cannot reach. In the efficiency-first system the battery shifts midday PV surplus to the evening and night; \nUBatNightTwentyE\% of its discharge occurs in hours without PV output, and it performs about \nUCyclesTwentyE\ equivalent full cycles per year (\nUCyclesTwentyS\ in the supply-only system). In the dry season, exports are limited by the annual net-metering constraint, so part of the midday surplus is curtailed: \nUCurtTwentyE\% of annual PV output with efficiency and \nUCurtTwentyS\% without it. In the shift weeks, round-the-clock production raises night demand, the battery is emptied every night and the grid covers the remainder. Both systems import the same \nUImpTwentyE~MWh allowed by the cap. Because efficiency lowers consumption in every hour, the efficiency-first system meets the cap with a smaller array, half the storage and much less curtailment.

\begin{figure}[H]
\begin{adjustwidth}{-\extralength}{0cm}
\centering
\includegraphics[width=\linewidth]{figures/fig10_urbs_dispatch.pdf}
\end{adjustwidth}
\caption{Hourly operation of the cost-optimal systems for a 20\% emission cap: (a,c) supply only; (b,d) efficiency available.}
\label{fig:urbsdispatch}
\end{figure}

\subsubsection{Battery cost}
Table~\ref{tab:urbsbat} repeats the optimisation with lower battery costs. Without an emission cap, batteries do not enter the optimum even at a quarter of the central cost, because under annual net metering the grid acts as a free and lossless store. Under a 20\% cap, halving the battery cost changes the optimal storage to \nUBatTwentyHalfE~kWh with efficiency and \nUBatTwentyHalfS~kWh without it, and at a quarter of the cost to \nUBatTwentyQuarterE\ and \nUBatTwentyQuarterS~kWh. Even then, efficiency lowers the annualised cost by \nUCostTwentyQuarterSave\%. Cheaper storage therefore does not displace efficiency; efficiency reduces both the storage required and the cost of every step along the frontier.

\input{tables/urbs_battery.tex}

"""

DISCUSSION = r"""\subsection{What formal optimisation adds}
The urbs results support the sequencing rule and refine it. In the linear programme, efficiency is not placed first by assumption: it competes with PV, storage and grid purchases in every hour, and the optimiser chooses it first. Its order of adoption reproduces the conservation supply curve. Base-load control and insulation are adopted in every scenario, and the servo motors and the compressed-air package are adopted as soon as the value of PV output falls below the tariff. Under generous annual net metering, PV output is worth the full tariff, so the two measures whose CCE is slightly above the PV LCOE are not selected even though each is profitable on its own (Table~\ref{tab:measures}); the ranking between PV and these two measures is also uncertain in the Monte Carlo analysis. When roof area, export compensation or an emission cap binds, the efficiency bundle enters first (in full from a 30\% cap) and lowers the cost of every subsequent step. These conditions characterise the deeper stages of decarbonisation, and the steps include the storage that physical self-sufficiency requires. Efficiency first is therefore an emergent property of least-cost design under constraints, not only a normative principle.

The optimisation also shows where the heuristic methods are sufficient and where they are not. The supply-only net-zero design of the linear programme coincides with that of the hourly design search, which the toolkit implements and which handles the monthly credit bank and the three billing rules explicitly. For shallow targets, sizing PV after efficiency and following the merit order therefore capture the main trade-offs. For deep targets, the joint optimisation is needed. It coordinates measures, PV, storage and curtailment hour by hour, and it reveals that the cost of the last tonnes of CO$_2$ is dominated by storage, which efficiency reduces but cannot remove. For SMEs facing emission targets from customers or lenders, this suggests a two-stage planning process. Simple tools can screen measures and size PV; an energy-system model such as urbs can then be used once storage or emission caps enter the decision.

"""

LIMITATION = r"""\item \emph{Linear programme.} The urbs model optimises one representative year with perfect foresight, values grid electricity at a constant marginal price, represents net metering as annual netting without the 12-month expiry of credits, omits PV degradation and battery ageing and allows partial adoption of measures. It is used to test the design logic and to trace the decarbonisation frontier rather than to size equipment exactly.
"""

CONCLUSION = r"""\item \emph{Joint optimisation.} In an urbs linear programme that co-optimises the measures, PV, storage and hourly operation, the efficiency bundle is completed before storage is added. Under emission caps of 35--10\% of the baseline it lowers the annualised cost by \nUCapSaveMin--\nUCapSaveMax\% and delays and shrinks the battery, which dominates the cost of deep decarbonisation.
"""
