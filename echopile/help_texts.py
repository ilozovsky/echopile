"""Short hover help texts for UI controls."""

from __future__ import annotations


HELP_TEXTS = {
    "amplification": (
        "Exponential time gain applied to the signal amplitude: "
        "A_out(t) = A_in(t) * exp(a0 * t). The slider controls the gain "
        "parameter a0."
    ),
    "signal_end": (
        "Maximum signal length kept for display and processing. The limit "
        "is applied after the current zero shift. Data beyond this limit "
        "are excluded from further processing and from the SLT."
    ),
    "signal_window": (
        "Enables advanced tail shaping after the selected signal end has been "
        "applied. A smooth taper is applied only at the right edge of the "
        "processed signal. Optional symmetric zero padding is used only as "
        "temporary support for edge-sensitive operations and is always "
        "removed before the final signal is displayed."
    ),
    "signal_window_taper": (
        "Length of the right-edge taper applied after amplification, signal "
        "end cutting, and optional detrending after amplification. Larger "
        "values suppress end-of-signal edge artifacts more strongly, but also "
        "attenuate more of the signal tail."
    ),
    "signal_window_padding": (
        "Temporary symmetric zero padding added after the right-edge taper for "
        "edge-sensitive operations such as filtering after amplification and "
        "SLT calculation. The padded zeros are never kept in the final "
        "processed signal or visible x-axis."
    ),
    "averaging_window": (
        "Window length used to average multiple loaded signals. The "
        "average is computed with a moving window along the x-axis: time "
        "values are averaged by a rolling median and amplitudes by a "
        "rolling mean. Larger windows produce smoother average traces but "
        "reduce local detail."
    ),
    "smoothing": (
        "Spline smoothing applied to the averaged trace only. A cubic "
        "B-spline is fitted to the average trace with a smoothing factor "
        "controlled by the slider. Larger values produce a smoother "
        "average trace, but can suppress local detail."
    ),
    "wave_speed": (
        "Wave speed used to convert the x-axis from time to pile length: "
        "L = t * WS / 2."
    ),
    "pile_length_marker": (
        "Position of a vertical reference line on the plots. Use it to "
        "mark the expected pile length, the depth of a suspected defect, "
        "or any other reference depth or time."
    ),
    "multiple_reflections": (
        "Spacing used to draw repeated vertical reference lines on the "
        "plots. Each line is placed at an integer multiple of this value. "
        "Use it to check whether anomalies appear at repeated intervals, "
        "which can help distinguish multiple reflections from one "
        "reflector."
    ),
    "generic_marker": (
        "Position of a generic vertical marker stored internally in ms and "
        "displayed in the current x-axis unit. Use it to mark a suspected "
        "defect or any other user-defined reference position."
    ),
    "generic_marker_label": (
        "Optional text shown next to the generic marker. Leave blank to draw "
        "the line without an annotation."
    ),
    "show_markers": (
        "Shows markers at the detected local maxima and minima of "
        "the processed signal on the main plot."
    ),
    "simplify_plot": (
        "Enables display simplification of the main signal plot. "
        "This can make plotting faster, but some visual details may "
        "be lost. It affects only the plot display, not the "
        "processing."
    ),
    "show_legend": (
        "Shows or hides the legend in the signal and spectrum plots. "
        "This does not affect processing, only the plot display."
    ),
    "text_file_time_unit": (
        "Time unit of the input time values in plain text files. Use this "
        "setting when the file does not define the time unit clearly."
    ),
    "assumed_signal_type": (
        "Detected or assumed physical signal type for each loaded file, "
        "such as acceleration or velocity. It is used mainly to "
        "determine the default number of integrations in Auto mode."
    ),
    "integration": (
        "Controls how many times the signal is integrated. Auto uses the "
        "default integration inferred for each file, while Off, x1, and "
        "x2 override it. For example, x1 transforms acceleration to "
        "velocity, and x2 transforms acceleration to displacement. Test "
        "signals are usually analyzed in velocity."
    ),
    "integration_method": (
        "Selects how the signal is integrated when integration is enabled. "
        "Time-domain integration is the standard direct integration of the "
        "signal. Frequency-domain integration is often preferred when "
        "low-frequency drift needs to be suppressed before integration. In "
        "this mode, Low-frequency suppression, Hz defines the cutoff below "
        "which spectral components are attenuated."
    ),
    "superlet_main": (
        "Time-frequency analysis based on superlets. A superlet combines "
        "several Morlet wavelets with different numbers of cycles at the "
        "same central frequency to improve frequency resolution while "
        "preserving good time resolution. Moca et al., 2021: "
        "https://doi.org/10.1038/s41467-020-20539-9"
    ),
    "freq_slt_min": (
        "Lowest frequency included in the SLT. Lower values extend the SLT "
        "plot downward."
    ),
    "freq_slt_max": (
        "Highest frequency included in the SLT. Values above the usable "
        "sampling limit are capped automatically."
    ),
    "freq_slt_no": (
        "Number of logarithmically spaced frequency samples between Min "
        "freq and Max freq. More samples give finer vertical detail, but "
        "increase computation time."
    ),
    "slt_mode": (
        "Selects whether the same superlet order is used for all frequencies "
        "(fixed SLT) or the order increases across frequency from Min order "
        "to Max order (fractional adaptive SLT, FASLT)."
    ),
    "cycle_scaling": (
        "Selects how the number of cycles grows across the wavelets in a "
        "superlet. In multiplicative mode, the i-th wavelet uses c_i = i * c_1. "
        "In additive mode, it uses c_i = c_1 + i - 1."
    ),
    "slt_output": (
        "Selects which part of the complex SLT response is shown: Power, "
        "Phase, absolute value, real part, or imaginary part."
    ),
    "colorscale": (
        "Colorscale for the SLT plot. Adjust low and high limits to "
        "highlight the value range of interest."
    ),
    "log_colorscale": (
        "Displays the SLT colors on a base-10 logarithmic scale. This is "
        "only available for nonnegative magnitude views such as Power and "
        "Amp, where it helps reveal weaker components next to strong ones."
    ),
    "slt_log_floor_exp": (
        "Base-10 exponent of the relative floor used for SLT log-color "
        "display. The actual floor ratio is 10^exp. For example, -6 means "
        "a floor of 1e-6 relative to the current positive maximum."
    ),
    "base_cycles": (
        "Number of cycles in the base Morlet wavelet. Lower values improve "
        "time localization, while higher values improve frequency "
        "resolution. A superlet of order 1 is a single base wavelet with "
        "this number of cycles."
    ),
    "order_fixed": (
        "Superlet order used in fixed SLT mode. The order is the number of "
        "wavelets in the set. Higher order improves frequency resolution, "
        "but can reduce time localization."
    ),
    "order_min": (
        "Lowest superlet order used in adaptive SLT. The order is the "
        "number of wavelets in the set. Lower frequencies start from this "
        "order."
    ),
    "order_max": (
        "Highest superlet order used in adaptive SLT. The order is the "
        "number of wavelets in the set. Higher frequencies can grow up to "
        "this order."
    ),
    "k_sd": (
        "Gaussian width parameter of the Morlet wavelet. It sets how "
        "many standard deviations of the Gaussian envelope contain the "
        "wavelet cycles."
    ),
    "support_sd": (
        "Finite numerical support of the Morlet wavelet, measured in Gaussian "
        "standard deviations. Higher values keep more of the wavelet tail and "
        "reduce truncation effects, but increase computation time."
    ),
    "superlet_coi_mask": (
        "Mask edge-affected pixels in the SLT heatmap. For each frequency, "
        "the edge half-width equals the support of the highest-order wavelet "
        "at that frequency: half = ceil(support_sd/2 * c_max / (k_sd * f * dt)). "
        "This is conservative: it hides all pixels where any contributing "
        "wavelet partially falls outside the signal. Masked pixels appear "
        "transparent. Because low frequencies have wide wavelets, the masked "
        "edges can be wide; increase the signal length or raise the minimum "
        "SLT frequency to reduce this."
    ),
    "superlet_attributes": (
        "Extract one or more 1D curves from the cached SLT matrix. Non-phase "
        "metrics are reduced over a selected frequency band, while Phase uses "
        "a single selected frequency row. The resulting curves can then be "
        "optionally averaged along the x-axis with a running mean or median."
    ),
    "superlet_attribute_placement": (
        "Choose whether the 1D SLT curves are drawn on top of the signal "
        "subplot or in a dedicated subplot below the SLT. The dedicated "
        "subplot is the default because it keeps axes clearer when several "
        "metrics are plotted together."
    ),
    "superlet_attribute_keys": (
        "Select one or more SLT-derived curves to plot together. Power and "
        "Amp use band-reduced magnitude information, Re and Im show signed "
        "components, and Phase uses a single selected frequency."
    ),
    "superlet_attr_normalize": (
        "Normalize each non-phase curve by its maximum absolute finite value. "
        "This makes different metrics easier to compare on the same subplot."
    ),
    "superlet_attr_freq_reduce": (
        "Reducer used across frequency rows inside the selected band for "
        "non-phase SLT metrics."
    ),
    "superlet_attr_x_reduce": (
        "Reducer used by the optional running window applied along the x-axis "
        "after each 1D SLT curve has been extracted."
    ),
    "superlet_attr_x_window": (
        "Length of the optional running window applied to each extracted 1D "
        "SLT curve along the x-axis. The stored value is in ms and follows "
        "the current ms/m UI conversion."
    ),
    "filter_settings": (
        "Applies a digital Butterworth filter to the signal. Low-pass and "
        "high-pass cutoff frequencies define the passband, and Filter order "
        "controls the filter steepness. High-pass filtering can suppress slow "
        "baseline drift and very low-frequency trends, while low-pass "
        "filtering can suppress high-frequency noise. The filter is "
        "implemented in second-order sections (SOS)."
    ),
    "advanced_filter_settings": (
        "Forward-backward filtering gives zero-phase filtering; otherwise "
        "it is applied once in the forward direction. The frequency-response "
        "plot shows the filter magnitude response."
    ),
    "local_extrema_settings": (
        "Controls how local maxima and minima are detected in the processed "
        "signal. These extrema are used to place marker symbols, estimate "
        "the automatic zero shift, and normalize the trace by the same "
        "reference peak. Distance and widths are given in samples, not in "
        "ms or m. Increase Min. distance if noise creates too many closely "
        "spaced peaks. Increase Min. width or decrease Max. width to reject "
        "peaks with unrealistic widths. Increase Min. prominence to ignore "
        "small fluctuations, and decrease it to keep weaker but potentially "
        "meaningful reflections. Change these settings only if peak "
        "detection is clearly unstable or misses important reflections."
    ),
    "downsampling": (
        "Reduces the sampling rate by keeping every n-th sample after "
        "optional anti-alias filtering. The Downsampling factor sets this "
        "integer decimation ratio. Larger values reduce the number of "
        "samples and speed up processing, but also reduce time resolution. "
        "The app limits the allowed factor automatically from the current "
        "signal sampling and processing settings, and suggests a default "
        "value when a file is loaded. If Anti-alias filter is enabled, the "
        "signal is first low-pass filtered before decimation. Use larger "
        "factors only when the signal is oversampled and fine time detail "
        "is not critical."
    ),
    "detrend": (
        "Removes a linear trend from the signal amplitude, either before or "
        "after amplification and signal-end trimming. This can reduce slow "
        "baseline drift, but its effect depends on the signal and should be "
        "checked visually. In many practical cases, simple high-pass "
        "filtering may be a more predictable way to suppress low-frequency "
        "drift."
    ),
    "zero_baseline": (
        "Subtracts from the whole signal a baseline estimated from the first "
        "few samples. This can correct a constant offset, but it does not "
        "remove a linear trend."
    ),
    "shift_signal": (
        "Moves the signal origin to the earliest detected reference peak in "
        "the first 30% of the signal. This defines the zero point used for "
        "pile-length estimation and helps align traces for comparison and "
        "averaging."
    ),
    "flip_polarity": (
        "Inverts the sign of the whole signal amplitude. Use this only to "
        "match the desired sign convention."
    ),
    "reverse_y_axis": (
        "Displays the amplitude axis upside down. This changes only the plot "
        "appearance."
    ),
}
