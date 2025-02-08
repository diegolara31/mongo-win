import javax.swing.*;
import java.awt.*;
import java.awt.event.*;
import java.io.*;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Main class to run the GUI application.
 */
public class Main {
    public static void main(String[] args) {
        // Set system look and feel
        try {
            UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName());
        } catch (Exception e) {
            e.printStackTrace();
        }

        // Check if running on Windows
        if (!System.getProperty("os.name").toLowerCase().contains("win")) {
            JFrame warningFrame = new JFrame("Warning");
            warningFrame.setUndecorated(true);
            warningFrame.setSize(400, 100);
            warningFrame.setLocationRelativeTo(null);

            JPanel panel = new JPanel(new BorderLayout());
            panel.setBorder(BorderFactory.createEmptyBorder(20, 20, 20, 20));

            JLabel warningLabel = new JLabel("This application only runs on Windows!", SwingConstants.CENTER);
            warningLabel.setFont(new Font("Arial", Font.BOLD, 14));
            warningLabel.setForeground(Color.RED);
            panel.add(warningLabel, BorderLayout.CENTER);

            warningFrame.add(panel);
            warningFrame.setVisible(true);

            // Close the application after 5 seconds
            Timer timer = new Timer(5000, e -> {
                warningFrame.dispose();
                System.exit(0);
            });
            timer.setRepeats(false);
            timer.start();
            return;
        }

        // Launch the GUI on the Event Dispatch Thread
        SwingUtilities.invokeLater(() -> {
            MainFrame mainFrame = new MainFrame();
            mainFrame.setVisible(true);
        });
    }
}

/**
 * The main window with service controls for MongoDB and Apache.
 */
class MainFrame extends JFrame {

    // Store service status labels by service name for bulk updates
    private final Map<String, JLabel> serviceStatusLabels = new HashMap<>();

    public MainFrame() {
        setTitle("DevTool");
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setSize(600, 350); // Updated height to make room for the new buttons
        setLocationRelativeTo(null);
        setLayout(new BorderLayout());

        // MongoDB configuration
        String mongoStartCmd = "mongodb\\bin\\mongod.exe --dbpath=mongodb\\local --logpath=mongodb\\mongo.log --logappend";
        String mongoStopCmd = "taskkill /F /IM mongod.exe";

        // Apache configuration
        String apacheStartCmd = "apache\\bin\\httpd.exe -d apache\\";
        String apacheStopCmd = "taskkill /F /IM httpd.exe";

        // Service Panels
        JPanel servicesPanel = new JPanel(new GridLayout(2, 1, 10, 10));
        servicesPanel.add(createServicePanel("MongoDB", mongoStartCmd, mongoStopCmd, "mongodb\\mongo.log"));
        servicesPanel.add(createServicePanel("Apache", apacheStartCmd, apacheStopCmd, "apache\\logs\\error.log"));
        add(servicesPanel, BorderLayout.CENTER);

        // Add the "Start All", "Stop All", and "Restart All" buttons
        JPanel actionPanel = new JPanel(new FlowLayout(FlowLayout.CENTER, 10, 10));
        JButton startAllButton = createButton("Start All", new Color(76, 175, 80));
        JButton stopAllButton = createButton("Stop All", new Color(244, 67, 54));
        JButton restartAllButton = createButton("Restart All", new Color(33, 150, 243));

        // Add action to buttons
        startAllButton.addActionListener(e -> handleStartAll(mongoStartCmd, apacheStartCmd));
        stopAllButton.addActionListener(e -> handleStopAll(mongoStopCmd, apacheStopCmd));
        restartAllButton.addActionListener(e -> handleRestartAll(mongoStartCmd, mongoStopCmd, apacheStartCmd, apacheStopCmd));

        actionPanel.add(startAllButton);
        actionPanel.add(stopAllButton);
        actionPanel.add(restartAllButton);

        add(actionPanel, BorderLayout.SOUTH);

        // Add window listener to handle cleanup
        addWindowListener(new WindowAdapter() {
            @Override
            public void windowClosing(WindowEvent e) {
                cleanup();
            }
        });
    }

    /**
     * Creates a service panel with Start, Stop, Restart, and Logs buttons.
     */
    private JPanel createServicePanel(String serviceName, String startCmd, String stopCmd, String logFilePath) {
        JPanel panel = new JPanel(new BorderLayout(10, 0));
        panel.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createEmptyBorder(5, 5, 5, 5),
                BorderFactory.createLineBorder(Color.LIGHT_GRAY)
        ));

        // Service name label with icon
        JLabel serviceLabel = new JLabel(serviceName);
        serviceLabel.setFont(new Font("Arial", Font.BOLD, 14));
        serviceLabel.setIcon(UIManager.getIcon("FileView.computerIcon"));
        serviceLabel.setBorder(BorderFactory.createEmptyBorder(0, 10, 0, 0));
        panel.add(serviceLabel, BorderLayout.WEST);

        // Status indicator
        JLabel statusLabel = new JLabel("●");
        statusLabel.setForeground(Color.RED);
        statusLabel.setToolTipText("Service Status: Stopped");
        panel.add(statusLabel, BorderLayout.CENTER);

        // Save this status label in our map for bulk updates
        serviceStatusLabels.put(serviceName, statusLabel);

        // Buttons panel
        JPanel buttonPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT, 5, 0));
        JButton startButton = createButton("Start", new Color(76, 175, 80));
        JButton stopButton = createButton("Stop", new Color(244, 67, 54));
        JButton restartButton = createButton("Restart", new Color(33, 150, 243));
        JButton explorerButton = createButton("Files", new Color(255, 193, 7));  // New Button
        JButton logsButton = createButton("Logs", new Color(158, 158, 158));

        // Actions for buttons
        startButton.addActionListener(e -> {
            updateStatus(statusLabel, Color.ORANGE, "Service Status: Starting...");
            executeCommand(startCmd, "Starting " + serviceName, serviceName + " Started", null, false, serviceName, () -> {
                updateStatus(statusLabel, new Color(76, 175, 80), "Service Status: Running");
            });
        });

        stopButton.addActionListener(e -> {
            updateStatus(statusLabel, Color.ORANGE, "Service Status: Stopping...");
            executeCommand(stopCmd, "Stopping " + serviceName, serviceName + " Stopped", logFilePath, true, serviceName, () -> {
                updateStatus(statusLabel, Color.RED, "Service Status: Stopped");
            });
        });

        restartButton.addActionListener(e -> handleRestart(serviceName, startCmd, stopCmd, logFilePath, statusLabel));

        // Open Explorer - Action for the new button
        explorerButton.addActionListener(e -> openExplorer(logFilePath));

        logsButton.addActionListener(e -> showLogs(logFilePath, serviceName));

        // Add buttons in order
        buttonPanel.add(startButton);
        buttonPanel.add(stopButton);
        buttonPanel.add(restartButton);
        buttonPanel.add(explorerButton);  // Add new Explorer button
        buttonPanel.add(logsButton);
        panel.add(buttonPanel, BorderLayout.EAST);

        return panel;
    }

    private JButton createButton(String text, Color color) {
        JButton button = new JButton(text);
        button.setBackground(color);
        button.setForeground(Color.WHITE);
        button.setFocusPainted(false);
        button.setBorderPainted(false);
        button.setOpaque(true);
        return button;
    }

    /**
     * Update the status label color and tooltip.
     */
    private void updateStatus(JLabel label, Color color, String tooltip) {
        SwingUtilities.invokeLater(() -> {
            label.setForeground(color);
            label.setToolTipText(tooltip);
        });
    }

    private void openExplorer(String filePath) {
        try {
            // Get the parent directory of the log file
            File directory = new File(filePath).getParentFile();
            if (directory != null && directory.exists()) {
                Desktop.getDesktop().open(directory); // Open the explorer at the directory
            } else {
                showError("Directory does not exist: " + filePath);
            }
        } catch (Exception ex) {
            handleError("Failed to open explorer", ex);
        }
    }

    private void handleRestart(String serviceName, String startCmd, String stopCmd, String logFilePath, JLabel statusLabel) {
        new Thread(() -> {
            try {
                updateStatus(statusLabel, Color.ORANGE, "Service Status: Restarting");

                // Stop service
                executeCommand(stopCmd, "Stopping " + serviceName, "Stopping " + serviceName, logFilePath, true, serviceName, null);
                Thread.sleep(2000);

                // Start service
                executeCommand(startCmd, "Starting " + serviceName, serviceName + " Restarted", null, false, serviceName, () -> {
                    updateStatus(statusLabel, new Color(76, 175, 80), "Service Status: Running");
                });
            } catch (InterruptedException ex) {
                handleError("Error during restart", ex);
                updateStatus(statusLabel, Color.RED, "Service Status: Error");
            }
        }).start();
    }

    private void handleStartAll(String mongoStartCmd, String apacheStartCmd) {
        JDialog progressDialog = createProgressDialog("Starting all services...");
        Timer autoCloseTimer = new Timer(3000, e -> progressDialog.dispose());
        autoCloseTimer.setRepeats(false);
        autoCloseTimer.start();

        new Thread(() -> {
            try {
                // Update status indicators to indicate starting
                updateStatus(serviceStatusLabels.get("MongoDB"), Color.ORANGE, "Service Status: Starting");
                updateStatus(serviceStatusLabels.get("Apache"), Color.ORANGE, "Service Status: Starting");

                // Start MongoDB
                executeCommand(mongoStartCmd, null, null, null, false, "MongoDB", null);

                // Start Apache
                executeCommand(apacheStartCmd, null, null, null, false, "Apache", null);

                SwingUtilities.invokeLater(() -> {
                    progressDialog.dispose();
                    // Update service status indicators to green (Running)
                    updateStatus(serviceStatusLabels.get("MongoDB"), new Color(76, 175, 80), "Service Status: Running");
                    updateStatus(serviceStatusLabels.get("Apache"), new Color(76, 175, 80), "Service Status: Running");
                    showSuccess("All services started successfully!");
                    autoCloseTimer.stop();
                });
            } catch (Exception e) {
                SwingUtilities.invokeLater(() -> {
                    progressDialog.dispose();
                    showError("Failed to start all services. Error: " + e.getMessage());
                    autoCloseTimer.stop();
                });
            }
        }).start();
    }

    private void handleStopAll(String mongoStopCmd, String apacheStopCmd) {
        JDialog progressDialog = createProgressDialog("Stopping all services...");
        new Thread(() -> {
            try {
                // Update status indicators to indicate stopping
                updateStatus(serviceStatusLabels.get("MongoDB"), Color.ORANGE, "Service Status: Stopping");
                updateStatus(serviceStatusLabels.get("Apache"), Color.ORANGE, "Service Status: Stopping");

                // Stop MongoDB (exit code 1 is allowed)
                executeCommand(mongoStopCmd, null, null, null, false, "MongoDB", null);

                // Stop Apache (exit code 1 is allowed)
                executeCommand(apacheStopCmd, null, null, null, false, "Apache", null);

                SwingUtilities.invokeLater(() -> {
                    progressDialog.dispose();
                    // Update statuses to stopped
                    updateStatus(serviceStatusLabels.get("MongoDB"), Color.RED, "Service Status: Stopped");
                    updateStatus(serviceStatusLabels.get("Apache"), Color.RED, "Service Status: Stopped");
                    showSuccess("All services stopped successfully!");
                });
            } catch (Exception e) {
                SwingUtilities.invokeLater(() -> {
                    progressDialog.dispose();
                    showError("Failed to stop all services. Error: " + e.getMessage());
                });
            }
        }).start();
    }

    private void handleRestartAll(String mongoStartCmd, String mongoStopCmd,
                                  String apacheStartCmd, String apacheStopCmd) {
        JDialog progressDialog = createProgressDialog("Restarting all services...");
        new Thread(() -> {
            try {
                // Update service status indicators to orange (Restarting)
                updateStatus(serviceStatusLabels.get("MongoDB"), Color.ORANGE, "Service Status: Restarting");
                updateStatus(serviceStatusLabels.get("Apache"), Color.ORANGE, "Service Status: Restarting");

                // Restart MongoDB
                executeCommand(mongoStopCmd, null, null, null, false, "MongoDB", null);
                executeCommand(mongoStartCmd, null, null, null, false, "MongoDB", null);

                // Restart Apache
                executeCommand(apacheStopCmd, null, null, null, false, "Apache", null);
                executeCommand(apacheStartCmd, null, null, null, false, "Apache", null);

                SwingUtilities.invokeLater(() -> {
                    progressDialog.dispose();
                    // Update service status indicators to green (Running)
                    updateStatus(serviceStatusLabels.get("MongoDB"), new Color(76, 175, 80), "Service Status: Running");
                    updateStatus(serviceStatusLabels.get("Apache"), new Color(76, 175, 80), "Service Status: Running");
                    showSuccess("All services restarted successfully!");
                });
            } catch (Exception e) {
                SwingUtilities.invokeLater(() -> {
                    progressDialog.dispose();
                    showError("Failed to restart all services. Error: " + e.getMessage());
                });
            }
        }).start();
    }

    /**
     * Executes a command and optionally runs a callback when complete.
     *
     * @param command            the command string
     * @param intermediateMessage message to show in the progress dialog while processing (can be null)
     * @param finalMessage       message to show on successful completion (can be null)
     * @param logFilePath        path to a log file to clear when stopping (can be null)
     * @param clearLogsOnStop    if true, clears the log file after stopping
     * @param serviceName        the name of the service (used for logging)
     * @param onComplete         a Runnable to execute on completion (may be null)
     */
    private void executeCommand(String command, String intermediateMessage, String finalMessage,
                                String logFilePath, boolean clearLogsOnStop, String serviceName,
                                Runnable onComplete) {
        // Create the waiting dialog
        final JDialog progressDialog = (intermediateMessage != null) ? createProgressDialog(intermediateMessage) : null;

        // Start a Timer to auto-close the progress dialog after 3 seconds
        Timer autoCloseTimer = new Timer(3000, e -> {
            if (progressDialog != null) {
                progressDialog.dispose();
            }
            if (finalMessage != null) {
                // Show a success message after dialog closes
                showSuccess(finalMessage);
            }
            if (onComplete != null) {
                onComplete.run(); // Call callback to update status
            }
        });
        autoCloseTimer.setRepeats(false); // Only run once

        new Thread(() -> {
            try {
                // Parse the command into parts
                List<String> commandList = parseCommand(command);
                ProcessBuilder processBuilder = new ProcessBuilder(commandList);
                processBuilder.redirectErrorStream(true);

                // Start process and read output asynchronously
                Process process = processBuilder.start();
                StreamGobbler outputGobbler = new StreamGobbler(process.getInputStream());
                outputGobbler.start();

                // Start the auto-close timer for the progress dialog
                autoCloseTimer.start();

                // Wait for the process to complete in the background
                int exitCode = process.waitFor();

                if (command.toLowerCase().contains("taskkill") && exitCode == 1) {
                    exitCode = 0; // Suppress the taskkill exit code 1
                }

                // Handle logs and completion callback
                int finalExitCode = exitCode;
                SwingUtilities.invokeLater(() -> {
                    if (finalExitCode == 0) {
                        // Reset logs on stop if requested
                        if (clearLogsOnStop && logFilePath != null) {
                            clearLogs(logFilePath);
                        }
                    } else {
                        // Log failure silently (or implement error support as needed)
//                    showError("Command failed with exit code: " + exitCode);
                    }
                });

            } catch (Exception ex) {
                SwingUtilities.invokeLater(() -> {
                    handleError("Error executing command", ex);
                    if (progressDialog != null) {
                        progressDialog.dispose();
                    }
                    autoCloseTimer.stop();
                });
            }
        }).start();
    }

    private List<String> parseCommand(String command) {
        List<String> commandList = new ArrayList<>();
        boolean inQuotes = false;
        StringBuilder current = new StringBuilder();

        for (char c : command.toCharArray()) {
            if (c == '"') {
                inQuotes = !inQuotes;
            } else if (c == ' ' && !inQuotes) {
                if (current.length() > 0) {
                    commandList.add(current.toString());
                    current.setLength(0);
                }
            } else {
                current.append(c);
            }
        }

        if (current.length() > 0) {
            commandList.add(current.toString());
        }

        return commandList;
    }

    private JDialog createProgressDialog(String message) {
        JDialog dialog = new JDialog(this, "Progress", false);
        JProgressBar progressBar = new JProgressBar();
        progressBar.setIndeterminate(true);

        JPanel panel = new JPanel(new BorderLayout(10, 10));
        panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10));
        panel.add(new JLabel(message), BorderLayout.NORTH);
        panel.add(progressBar, BorderLayout.CENTER);

        dialog.add(panel);
        dialog.pack();
        dialog.setLocationRelativeTo(this);
        dialog.setVisible(true);

        return dialog;
    }

    private void clearLogs(String logFilePath) {
        try {
            new FileWriter(logFilePath, false).close();
        } catch (IOException ex) {
            handleError("Error clearing logs", ex);
        }
    }

    private void showLogs(String logFilePath, String serviceName) {
        SwingUtilities.invokeLater(() -> {
            JFrame logFrame = new JFrame(serviceName + " Logs");
            logFrame.setSize(800, 600);
            logFrame.setLocationRelativeTo(this);

            JTextArea logArea = new JTextArea();
            logArea.setEditable(false);
            logArea.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));

            JScrollPane scrollPane = new JScrollPane(logArea);
            logFrame.add(scrollPane);

            // Add refresh button
            JButton refreshButton = new JButton("Refresh");
            refreshButton.addActionListener(e -> loadLogs(logFilePath, logArea));

            JPanel buttonPanel = new JPanel(new FlowLayout(FlowLayout.RIGHT));
            buttonPanel.add(refreshButton);
            logFrame.add(buttonPanel, BorderLayout.NORTH);

            loadLogs(logFilePath, logArea);
            logFrame.setVisible(true);
        });
    }

    private void loadLogs(String logFilePath, JTextArea logArea) {
        try (BufferedReader reader = new BufferedReader(new FileReader(logFilePath))) {
            String logs = reader.lines().collect(Collectors.joining("\n"));
            logArea.setText(logs);
            logArea.setCaretPosition(logArea.getDocument().getLength());
        } catch (IOException ex) {
            logArea.setText("Error reading log file: " + ex.getMessage());
        }
    }

    private void handleError(String message, Exception ex) {
        ex.printStackTrace();
        SwingUtilities.invokeLater(() -> showError(message + ": " + ex.getMessage()));
    }

    private void showError(String message) {
        JOptionPane.showMessageDialog(this, message, "Error", JOptionPane.ERROR_MESSAGE);
    }

    private void showSuccess(String message) {
        JOptionPane.showMessageDialog(this, message, "Success", JOptionPane.INFORMATION_MESSAGE);
    }

    private void cleanup() {
        executeCommand("taskkill /F /IM mongod.exe", "Stopping MongoDB", "MongoDB Stopped", null, false, "MongoDB", null);
        executeCommand("taskkill /F /IM Apache.exe", "Stopping Apache", "Apache Stopped", null, false, "Apache", null);
    }
}

/**
 * Helper class to gobble the output stream of a process.
 */
class StreamGobbler extends Thread {
    private final InputStream inputStream;

    public StreamGobbler(InputStream inputStream) {
        this.inputStream = inputStream;
    }

    @Override
    public void run() {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream))) {
            String line;
            while ((line = reader.readLine()) != null) {
                System.out.println(line);
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
