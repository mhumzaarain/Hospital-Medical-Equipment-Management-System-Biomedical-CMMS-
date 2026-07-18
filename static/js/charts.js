/* Theme-aware Chart.js wrapper. Load after chart.umd.js on pages with charts. */
(function () {
  const css = (name) =>
    getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const rebuilders = [];

  function tooltip() {
    return {
      backgroundColor: css("--chart-tooltip-bg"),
      titleColor: css("--chart-tooltip-fg"),
      bodyColor: css("--chart-tooltip-fg"),
      cornerRadius: 8,
      padding: 10,
      displayColors: false,
    };
  }

  function barConfig(data, horizontal) {
    return {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [{
          data: data.values,
          backgroundColor: css("--chart-bar"),
          hoverBackgroundColor: css("--chart-bar-hover"),
          borderRadius: 6,
          maxBarThickness: 42,
        }],
      },
      options: {
        indexAxis: horizontal ? "y" : "x",
        responsive: true,
        animation: reduced ? false : { duration: 800, easing: "easeOutQuart" },
        plugins: { legend: { display: false }, tooltip: tooltip() },
        scales: {
          x: {
            ticks: { color: css("--chart-tick") },
            grid: horizontal
              ? { color: css("--chart-grid") }
              : { display: false },
            border: { display: false },
            beginAtZero: true,
          },
          y: {
            ticks: { color: css("--chart-tick") },
            grid: horizontal
              ? { display: false }
              : { color: css("--chart-grid") },
            border: { display: false },
            beginAtZero: true,
          },
        },
      },
    };
  }

  function doughnutConfig(data) {
    const palette = [1, 2, 3, 4, 5, 6, 7, 8].map((i) => css("--chart-cat-" + i));
    return {
      type: "doughnut",
      data: {
        labels: data.labels,
        datasets: [{ data: data.values, backgroundColor: palette, borderWidth: 0 }],
      },
      options: {
        responsive: true,
        cutout: "65%",
        animation: reduced ? false : { duration: 800, easing: "easeOutQuart" },
        plugins: {
          legend: {
            display: true,
            position: "bottom",
            labels: { color: css("--chart-tick"), usePointStyle: true, boxWidth: 8 },
          },
          tooltip: tooltip(),
        },
      },
    };
  }

  window.hemdeskChart = function (canvasId, scriptId, kind) {
    /* json_script double-encodes because the view passes a JSON string. */
    const data = JSON.parse(JSON.parse(document.getElementById(scriptId).textContent));
    const make = () =>
      kind === "doughnut"
        ? doughnutConfig(data)
        : barConfig(data, kind === "bar-h");
    let chart = new Chart(document.getElementById(canvasId), make());
    rebuilders.push(() => {
      chart.destroy();
      chart = new Chart(document.getElementById(canvasId), make());
    });
  };

  window.addEventListener("theme-changed", () => rebuilders.forEach((fn) => fn()));
})();
