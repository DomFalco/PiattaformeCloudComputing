import logging
import time
import sys
import os
import yaml
import warnings

# Aggiungi percorso
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ignora warnings
warnings.filterwarnings("ignore")

# Importa componenti
from collector_ovs import NeutronOVSCollector
from detector import HybridAnomalyDetector
from reporter import AnomalyReporter

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def load_config(config_path='config.yaml'):
    #Carica configurazione
    default_config = {
        'openstack': {
            'auth_url': 'http://controller:5000/v3',
            'username': 'admin',
            'password': 'secret',
            'project_name': 'admin',
            'user_domain': 'Default',
            'project_domain': 'Default'
        },
        'monitoring': {
            'collection_interval': 30,
            'severity_threshold': 0.7,
            'max_anomalies_per_report': 20
        },
        'generator': {
            'enabled': True,
            'injection_rate': 0.3,
            'anomaly_ratio': 0.3
        },
        'output': {
            'save_reports': True,
            'report_directory': './reports',
            'log_level': 'INFO'
        }
    }
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
            
            # Merge ricorsivo
            def merge_dicts(default, user):
                for key, value in user.items():
                    if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                        merge_dicts(default[key], value)
                    else:
                        default[key] = value
                return default
            
            config = merge_dicts(default_config, user_config)
            logger.info(f"Config loaded from {config_path}")
        else:
            config = default_config
            logger.warning(f"Config file {config_path} not found, using defaults")
        
        return config
        
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return default_config

def print_banner():
    #Stampa banner
    print("\n" + "="*70)
    print("NEUTRON AI ANOMALY DETECTION - OVS REAL METRICS")
    print("="*70)
    print("Using REAL Open vSwitch traffic statistics")
    print("Isolation Forest anomaly detection")
    print("Automatic traffic generation (normal + anomalies)")
    print("Security monitoring for OpenStack networks")
    print("="*70 + "\n")

def main():
    #Funzione principale
    print_banner()
    
    # Carica configurazione
    config = load_config()
    
    # Inizializza componenti
    try:
        logger.info("Initializing components...")
        
        collector = NeutronOVSCollector(config)
        detector = HybridAnomalyDetector(config)
        reporter = AnomalyReporter(config.get('output', {}))
        
        logger.info("✅ All components initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        sys.exit(1)
    
    # Parametri
    collection_interval = config['monitoring']['collection_interval']
    severity_threshold = config['monitoring']['severity_threshold']
    
    logger.info("Starting automated network monitoring")
    logger.info(f"Collection interval: {collection_interval}s")
    logger.info(f"Severity threshold: {severity_threshold}")
    logger.info(f"Traffic generator: {'ENABLED' if config['generator']['enabled'] else 'DISABLED'}")
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            logger.info(f"\n🔄 Monitoring cycle #{cycle_count}")
            
            # Raccolta metriche
            start_time = time.time()
            try:
                features_data = collector.collect_metrics()
                collection_time = time.time() - start_time
                
                # Analizza composizione
                real_count = len([f for f in features_data if f.get('source') in ['ovs_real', 'neutron_estimate']])
                generated_count = len([f for f in features_data if 'generated' in f.get('source', '')])
                anomaly_count = len([f for f in features_data if 'generated_anomaly' in f.get('source', '')])
                
                logger.info(f"-------------------- Collected {len(features_data)} total metrics --------------------")
                logger.info(f"   Real: {real_count}, Generated: {generated_count}")
                logger.info(f"   Generated anomalies: {anomaly_count}")
                logger.info(f"   Collection time: {collection_time:.1f}s")
                
            except Exception as e:
                logger.error(f"Collection failed: {e}")
                features_data = []
                continue
            
            # Rilevamento anomalie
            if features_data:
                anomalies = detector.detect_anomalies(features_data)
                
                # Reporting
                if anomalies:
                    report = reporter.report_anomalies(anomalies, severity_threshold)
                    
                    # Salva report periodicamente
                    if config['output']['save_reports'] and cycle_count % 5 == 0:
                        report_dir = config['output']['report_directory']
                        os.makedirs(report_dir, exist_ok=True)
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        report_file = f"{report_dir}/anomaly_report_{timestamp}.json"
                        reporter.save_report_to_file(report, report_file)
                else:
                    logger.info("✅ No anomalies detected in this cycle")
            else:
                logger.warning("No metrics collected in this cycle")
            
            # Statistiche periodiche
            if cycle_count % 3 == 0:
                logger.info(f"-------------------- Statistics after {cycle_count} cycles: --------------------")
                logger.info(f"   Total anomalies detected: {reporter.total_anomalies}")
                logger.info(f"   Generated anomalies: {reporter.generated_anomalies}")
                logger.info(f"   Real anomalies: {reporter.real_anomalies}")
                
                # Statistiche generatore
                gen_stats = collector.get_generator_stats()
                if gen_stats['total_generated'] > 0:
                    anomaly_rate = gen_stats['anomalies_generated'] / gen_stats['total_generated']
                    logger.info(f"   Generator: {gen_stats['total_generated']} samples, "
                              f"{gen_stats['anomalies_generated']} anomalies "
                              f"({anomaly_rate:.1%})")
            
            # Attesa per prossimo ciclo
            logger.info(f"⏳ Next collection in {collection_interval} seconds...")
            time.sleep(collection_interval)
            
    except KeyboardInterrupt:
        logger.info("\n👋 Monitoring stopped by user")
        
        # Sommario finale
        logger.info("="*60)
        logger.info("-------------------- SESSION SUMMARY --------------------")
        logger.info("="*60)
        logger.info(f"Total monitoring cycles: {cycle_count}")
        logger.info(f"Total anomalies detected: {reporter.total_anomalies}")
        logger.info(f"Generated anomalies: {reporter.generated_anomalies}")
        logger.info(f"Real anomalies: {reporter.real_anomalies}")
        
        if reporter.total_anomalies > 0:
            detection_rate = reporter.generated_anomalies / max(1, reporter.total_anomalies)
            logger.info(f"Generated anomaly detection rate: {detection_rate:.1%}")
        
        logger.info(reporter.get_history_summary())
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
