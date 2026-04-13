(function () {
  function downloadPlotFromContainer(containerId) {
    const container = document.getElementById(containerId);
    if (!container || !window.Plotly) {
      return;
    }

    const graph = container.querySelector('.js-plotly-plot');
    if (!graph) {
      return;
    }

    const context = graph._context || {};
    const exportOptions = Object.assign({ format: 'png' }, context.toImageButtonOptions || {});
    window.Plotly.downloadImage(graph, exportOptions);
  }

  document.addEventListener('click', function (event) {
    if (event.target.closest('#btn-save-time-plot')) {
      downloadPlotFromContainer('time_plot');
      return;
    }

    if (event.target.closest('#btn-save-spectrum-plot')) {
      downloadPlotFromContainer('spectrum_plot');
    }
  });
})();
