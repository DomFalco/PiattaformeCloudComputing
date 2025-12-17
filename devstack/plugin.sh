#!/usr/bin/env bash
# plugin.sh - AI Anomaly Detection plugin for DevStack

function install_ai_anomaly_detector {
    echo_summary "Installing AI Anomaly Detection"
    
    # Install Python packages from YOUR requirements.txt
    if [ -f "$DEVSTACK_DIR/ai_anomaly_detection/requirements.txt" ]; then
        echo_summary "Installing from requirements.txt"
        pip_install -r $DEVSTACK_DIR/ai_anomaly_detection/requirements.txt
    else
        # Fallback: install core dependencies
        echo_summary "Installing core dependencies"
        pip_install pandas scikit-learn numpy pyyaml openstacksdk
    fi
    
    echo_summary "Copying AI Anomaly Detection project"
    # Create destination directory
    mkdir -p $DEST/ai_anomaly_detection
    
    # Copy ALL your files
    cp -r $DEVSTACK_DIR/ai_anomaly_detection/* $DEST/ai_anomaly_detection/
}

function init_ai_anomaly_detector {
    echo_summary "Starting AI Anomaly Detection service"
    
    # Change to your project directory
    cd $DEST/ai_anomaly_detection
    
    echo_summary "Running: python3 main.py"
    # Start your main application
    if [[ "$USE_SCREEN" == "True" ]]; then
        screen_it ai-anomaly "python3 main.py --config config.yaml"
    else
        # Start in background and save PID
        nohup python3 main.py --config config.yaml > anomaly.log 2>&1 &
        echo $! > /tmp/ai_anomaly.pid
        echo "AI Anomaly Detector started (PID: $!)"
    fi
}

function configure_ai_anomaly_detector {
    echo_summary "Configuring AI Anomaly Detection"
    
    # You can add configuration steps here if needed
    # For example: set up log rotation, create directories, etc.
    
    # Create log directory
    mkdir -p /var/log/ai_anomaly_detection 2>/dev/null || true
    
    # Set proper permissions
    chmod 644 $DEST/ai_anomaly_detection/config.yaml 2>/dev/null || true
}

# check for service enabled
if is_service_enabled ai-anomaly-detector; then

    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
        # Set up system services
        echo_summary "AI Anomaly Detection pre-installation"
        # Install system dependencies if needed
        # install_package python3-dev build-essential

    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing AI Anomaly Detection"
        install_ai_anomaly_detector

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after other services
        echo_summary "Configuring AI Anomaly Detection"
        configure_ai_anomaly_detector

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # Initialize and start the service
        echo_summary "Initializing AI Anomaly Detection"
        init_ai_anomaly_detector
    fi

    if [[ "$1" == "unstack" ]]; then
        # Shut down ai-anomaly-detector services
        echo_summary "Stopping AI Anomaly Detection"
        pkill -f "python3.*main.py" 2>/dev/null || true
        [ -f /tmp/ai_anomaly.pid ] && kill $(cat /tmp/ai_anomaly.pid) 2>/dev/null || true
        screen_stop ai-anomaly 2>/dev/null || true
        rm -f /tmp/ai_anomaly.pid 2>/dev/null || true
    fi

    if [[ "$1" == "clean" ]]; then
        # Remove state and transient data
        echo_summary "Cleaning AI Anomaly Detection"
        rm -f /tmp/ai_anomaly.pid 2>/dev/null || true
        rm -f $DEST/ai_anomaly_detection/anomaly.log 2>/dev/null || true
        # Remove the entire directory if you want
        # rm -rf $DEST/ai_anomaly_detection 2>/dev/null || true
    fi
fi
