let keySizeChart = null;
let latencyChart = null;

window.renderBenchmarkCharts = function() {
    renderKeySizeChart();
    renderLatencyChart();
};

function renderKeySizeChart() {
    const ctx = document.getElementById("chart-keysize");
    if (!ctx) return;

    if (keySizeChart) {
        keySizeChart.destroy();
    }

    keySizeChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["RSA-2048", "ECDSA (P-256)", "ML-KEM-768", "ML-DSA-65"],
            datasets: [
                {
                    label: "Public Key Size (Bytes)",
                    data: [256, 64, 1184, 1952],
                    backgroundColor: "rgba(59, 130, 246, 0.7)",
                    borderColor: "#3b82f6",
                    borderWidth: 1
                },
                {
                    label: "Ciphertext / Signature (Bytes)",
                    data: [256, 64, 1088, 3309],
                    backgroundColor: "rgba(16, 185, 129, 0.7)",
                    borderColor: "#10b981",
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: { color: "#94a3b8", font: { family: "-apple-system, sans-serif" } }
                }
            },
            scales: {
                x: {
                    ticks: { color: "#94a3b8" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" }
                },
                y: {
                    ticks: { color: "#94a3b8" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    title: { display: true, text: "Bytes", color: "#64748b" }
                }
            }
        }
    });
}

function renderLatencyChart(customData = null) {
    const ctx = document.getElementById("chart-latency");
    if (!ctx) return;

    if (latencyChart) {
        latencyChart.destroy();
    }

    const defaultData = [14.2, 18.5, 22.8];
    const dataToUse = customData || defaultData;

    latencyChart = new Chart(ctx, {
        type: "bar",
        data: {
            labels: [
                "Classical (ECDHE + ECDSA)",
                "Hybrid (X25519MLKEM768)",
                "Pure PQC (ML-KEM-768 + ML-DSA-65)"
            ],
            datasets: [
                {
                    label: "TLS 1.3 Handshake RTT (ms)",
                    data: dataToUse,
                    backgroundColor: [
                        "rgba(100, 116, 139, 0.7)",
                        "rgba(59, 130, 246, 0.7)",
                        "rgba(139, 92, 246, 0.7)"
                    ],
                    borderColor: ["#64748b", "#3b82f6", "#8b5cf6"],
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    ticks: { color: "#94a3b8" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" }
                },
                y: {
                    ticks: { color: "#94a3b8" },
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    title: { display: true, text: "Milliseconds (ms)", color: "#64748b" }
                }
            }
        }
    });
}

window.simulateHandshakeBenchmark = function() {
    const randomLatency = [
        (13.5 + Math.random() * 2).toFixed(1),
        (17.8 + Math.random() * 2.5).toFixed(1),
        (21.5 + Math.random() * 3).toFixed(1)
    ];

    renderLatencyChart(randomLatency);
};
