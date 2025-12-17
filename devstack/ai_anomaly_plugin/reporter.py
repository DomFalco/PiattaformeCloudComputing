import logging
import json
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class AnomalyReporter:
    def __init__(self, config=None):
        self.config = config or {}
        self.report_dir = self.config.get('report_directory', './reports')
        
        # Statistiche
        self.total_anomalies = 0
        self.generated_anomalies = 0
        self.real_anomalies = 0
        self.anomaly_history = []
        
        logger.info("->Reporter ready<-")
    
    def report_anomalies(self, anomalies: List[Dict], severity_threshold: float = 0.7):
        #Genera report per le anomalie
        if not anomalies:
            logger.info("✅ No anomalies to report")
            return None
        
        # Separa anomalie per tipo e severità
        critical_anomalies = [a for a in anomalies if a['anomaly_score'] >= severity_threshold]
        generated_anomalies = [a for a in anomalies if 'generated' in a.get('source', '')]
        real_anomalies = [a for a in anomalies if 'generated' not in a.get('source', '')]
        
        # Aggiorna statistiche
        self.total_anomalies += len(anomalies)
        self.generated_anomalies += len(generated_anomalies)
        self.real_anomalies += len(real_anomalies)
        
        # Crea report
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_anomalies': len(anomalies),
            'critical_anomalies': len(critical_anomalies),
            'generated_anomalies': len(generated_anomalies),
            'real_anomalies': len(real_anomalies),
            'anomaly_types': {},
            'details': []
        }
        
        # Conta tipi di anomalia
        for anomaly in anomalies:
            anomaly_type = anomaly.get('anomaly_type', 'UNKNOWN')
            report['anomaly_types'][anomaly_type] = report['anomaly_types'].get(anomaly_type, 0) + 1
        
        # Aggiungi dettagli per anomalie critiche
        for anomaly in critical_anomalies[:10]:  # Limita a 10
            is_generated = 'generated' in anomaly.get('source', '')
            
            detail = {
                'resource': anomaly['resource_name'],
                'type': anomaly.get('anomaly_type', 'UNKNOWN'),
                'score': anomaly['anomaly_score'],
                'method': anomaly.get('detection_method', 'unknown'),
                'source': 'GENERATED' if is_generated else 'REAL',
                'timestamp': anomaly.get('timestamp', datetime.utcnow().isoformat())
            }
            
            # Aggiungi dettagli specifici per anomalie generate
            if is_generated and 'raw_metrics' in anomaly:
                raw = anomaly['raw_metrics']
                if 'anomaly_type' in raw:
                    detail['generated_type'] = raw['anomaly_type']
                if 'description' in raw:
                    detail['description'] = raw['description']
            
            report['details'].append(detail)
        
        # Log del report
        self._log_report(report)
        
        # Salva in history
        self.anomaly_history.append({
            'timestamp': report['timestamp'],
            'total': len(anomalies),
            'critical': len(critical_anomalies),
            'generated': len(generated_anomalies),
            'real': len(real_anomalies)
        })
        
        return report
    
    def _log_report(self, report: Dict):
        #Log del report
        logger.info("="*60)
        logger.info("🚨 ANOMALY DETECTION REPORT")
        logger.info("="*60)
        logger.info(f"Timestamp: {report['timestamp']}")
        logger.info(f"Total anomalies: {report['total_anomalies']}")
        logger.info(f"Critical anomalies: {report['critical_anomalies']}")
        logger.info(f"[SIMULATED] Generated anomalies: {report['generated_anomalies']}")
        logger.info(f"[REAL] Real anomalies: {report['real_anomalies']}")
        
        if report['anomaly_types']:
            logger.info("-------------------- Anomaly types: --------------------")
            for anomaly_type, count in report['anomaly_types'].items():
                logger.info(f"   {anomaly_type}: {count}")
        
        if report['details']:
            logger.info("-------------------- Critical anomalies details: --------------------")
            for detail in report['details']:
                source_tag = "[SIMULATED]" if detail['source'] == 'GENERATED' else "[REAL]"
                logger.info(f"{source_tag}: "
                            f"{detail['type']} (score: {detail['score']:.2f})")
        
        logger.info("="*60)
    
    def save_report_to_file(self, report: Dict, filename: str):
        #Salva report su file
        try:
            import os
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"💾 Report saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving report: {e}")
    
    def get_history_summary(self):
        #Restituisce sommario storico
        if not self.anomaly_history:
            return "No anomaly history available"
        
        total_cycles = len(self.anomaly_history)
        total_anomalies = sum(h['total'] for h in self.anomaly_history)
        avg_anomalies = total_anomalies / total_cycles if total_cycles > 0 else 0
        
        summary = f"History: {total_cycles} cycles, {total_anomalies} total anomalies "
        summary += f"({avg_anomalies:.1f} avg/cycle)"
        
        return summary
    
    def reset_stats(self):
        #Resetta le statistiche
        self.total_anomalies = 0
        self.generated_anomalies = 0
        self.real_anomalies = 0
        self.anomaly_history = []
        logger.info("Statistics reset")
