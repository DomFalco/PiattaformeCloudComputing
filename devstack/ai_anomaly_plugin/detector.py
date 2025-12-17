import logging
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import pickle
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class HybridAnomalyDetector:
    def __init__(self, config=None):
        logger.info("->Initializing Hybrid AI Anomaly Detector...")

        self.real_traffic_history = []  # Memoria del traffico reale
        self.retrain_threshold = 50  # Ogni 50 campioni reali, riaddestra
        self.config = config or {}

        # Soglie per detection
        self.base_thresholds = {
            'bytes_in_kb': 5000.0,  # 5MB
            'bytes_out_kb': 4000.0,  # 4MB
            'packets_in': 10000.0,  # 10k pacchetti
            'packets_out': 8000.0,  # 8k pacchetti
            'drop_rate': 0.02,  # 2%
            'num_ports': 25.0,  # 25 porte
            'utilization': 0.85,  # 85%
            'active_status': 0.5  # Attivo se > 0.5
        }

        # Soglie per evitare falsi positivi
        self.adjusted_thresholds = self._calculate_adjusted_thresholds()

        # Aggiorna con config se presente
        if 'anomaly_detection' in self.config:
            config_thresholds = self.config['anomaly_detection'].get('thresholds', {})
            self.base_thresholds.update(config_thresholds)
            # Ricalcola le soglie
            self.adjusted_thresholds = self._calculate_adjusted_thresholds()

        # Modello ML
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False

        # File per persistenza
        self.model_file = 'isolation_forest_model.pkl'
        self.scaler_file = 'scaler.pkl'

        # Statistiche
        self.detection_stats = {
            'total_checked': 0,
            'threshold_anomalies': 0,
            'ml_anomalies': 0,
            'false_positives': 0
        }

        # Cerca modello salvato o addestra
        if self._model_files_exist():
            self._load_model()
        else:
            self._train_model()

        logger.info(f"Hybrid AI Anomaly Detector ready")
        logger.info(f"Base thresholds: {self.base_thresholds}")
        logger.info(f"Adjusted thresholds: {self.adjusted_thresholds}")

    def _calculate_adjusted_thresholds(self):
        # Soglie per detection
        return {
            'bytes_in_kb': self.base_thresholds['bytes_in_kb'] * 0.8,  # ML: 80%
            'bytes_out_kb': self.base_thresholds['bytes_out_kb'] * 0.8,  # ML: 80%
            'packets_in': self.base_thresholds['packets_in'] * 0.7,  # ML: 70%
            'packets_out': self.base_thresholds['packets_out'] * 0.7,  # ML: 70%
            'drop_rate': self.base_thresholds['drop_rate'] * 0.5,  # ML: 50%
            'num_ports': self.base_thresholds['num_ports'] * 0.9,  # ML: 90%
            'utilization': self.base_thresholds['utilization'] * 0.9,  # ML: 90%
            'active_status': self.base_thresholds['active_status'] * 1.2  # ML: 120%
        }

    def _retrain_incremental(self):
        # Ri-addestra il modello combinando dati sintetici e dati reali raccolti
        if not self.real_traffic_history:
            return

        logger.info(f"🔄 Adaptive Learning: Retraining model with {len(self.real_traffic_history)} real samples...")

        # Genera dati sintetici
        n_samples_synth = 500
        self._train_model(extra_data=self.real_traffic_history)

        #self.real_traffic_history = []  # in caso si voglia svuotare la memoria

    def _train_model(self, extra_data=None):
        # Addestra il modello Isolation Forest con dati più realistici
        logger.info("Training Isolation Forest model with realistic data...")

        n_samples = 1000
        n_features = 8

        # Dati normali
        X_normal = np.zeros((int(n_samples * 0.85), n_features))

        for i in range(X_normal.shape[0]):
            # Traffico normale
            base_traffic = np.random.exponential(scale=800)

            # Variazione oraria
            hour = np.random.randint(0, 24)
            time_factor = 1.5 if 9 <= hour <= 18 else 0.7

            bytes_in_kb = base_traffic * time_factor * np.random.uniform(0.5, 1.5)
            bytes_in_kb = min(bytes_in_kb, self.base_thresholds['bytes_in_kb'] * 0.6)

            bytes_out_kb = bytes_in_kb * np.random.uniform(0.5, 0.9)
            bytes_out_kb = min(bytes_out_kb, self.base_thresholds['bytes_out_kb'] * 0.6)

            avg_packet = np.random.uniform(500, 1500)
            packets_in = int(bytes_in_kb * 1024 / avg_packet)
            packets_out = int(bytes_out_kb * 1024 / avg_packet)

            packets_in = min(packets_in, self.base_thresholds['packets_in'] * 0.5)
            packets_out = min(packets_out, self.base_thresholds['packets_out'] * 0.5)

            # Drop rate basso per traffico normale
            drop_rate = np.random.beta(1, np.random.randint(500, 2000))

            # Altre feature realistiche
            num_ports = np.random.randint(2, 15)
            utilization = np.random.beta(2, np.random.randint(4, 10))
            active_status = 1.0 if np.random.random() > 0.1 else 0.0  # 90% attivo

            X_normal[i] = [
                bytes_in_kb, bytes_out_kb, packets_in, packets_out,
                drop_rate, num_ports, utilization, active_status
            ]

        # Dati anomali
        X_anomaly = np.zeros((int(n_samples * 0.15), n_features))

        for i in range(X_anomaly.shape[0]):
            anomaly_type = np.random.choice(['high_traffic', 'high_drop', 'many_ports', 'inactive', 'high_util'])

            if anomaly_type == 'high_traffic':
                bytes_in_kb = self.adjusted_thresholds['bytes_in_kb'] * np.random.uniform(1.2, 3.0)
                bytes_out_kb = self.adjusted_thresholds['bytes_out_kb'] * np.random.uniform(1.2, 2.5)
                packets_in = self.adjusted_thresholds['packets_in'] * np.random.uniform(1.3, 3.0)
                packets_out = self.adjusted_thresholds['packets_out'] * np.random.uniform(1.3, 2.5)
                drop_rate = np.random.beta(1, 100)  # 0.01 medio

            elif anomaly_type == 'high_drop':
                bytes_in_kb = np.random.exponential(scale=500)
                bytes_out_kb = bytes_in_kb * np.random.uniform(0.7, 0.9)
                packets_in = int(bytes_in_kb * 1024 / np.random.uniform(800, 1200))
                packets_out = int(bytes_out_kb * 1024 / np.random.uniform(800, 1200))
                drop_rate = np.random.uniform(0.05, 0.25)  # 5-25% (sopra soglia)

            elif anomaly_type == 'many_ports':
                bytes_in_kb = np.random.exponential(scale=600)
                bytes_out_kb = bytes_in_kb * np.random.uniform(0.7, 0.9)
                packets_in = int(bytes_in_kb * 1024 / np.random.uniform(800, 1200))
                packets_out = int(bytes_out_kb * 1024 / np.random.uniform(800, 1200))
                drop_rate = np.random.beta(1, 150)
                num_ports = self.adjusted_thresholds['num_ports'] * np.random.uniform(1.3, 2.0)

            elif anomaly_type == 'inactive':
                bytes_in_kb = 0
                bytes_out_kb = 0
                packets_in = 0
                packets_out = 0
                drop_rate = 0
                active_status = 0.0

            else:  # high_util
                bytes_in_kb = np.random.exponential(scale=700)
                bytes_out_kb = bytes_in_kb * np.random.uniform(0.7, 0.9)
                packets_in = int(bytes_in_kb * 1024 / np.random.uniform(800, 1200))
                packets_out = int(bytes_out_kb * 1024 / np.random.uniform(800, 1200))
                drop_rate = np.random.beta(1, 200)
                utilization = self.adjusted_thresholds['utilization'] * np.random.uniform(1.1, 1.3)

            if anomaly_type != 'inactive':
                num_ports = np.random.randint(5, 20)
                utilization = np.random.uniform(0.7, 0.95)
                active_status = 1.0
            else:
                num_ports = np.random.randint(1, 5)
                utilization = 0.0

            X_anomaly[i] = [
                bytes_in_kb, bytes_out_kb, packets_in, packets_out,
                drop_rate, num_ports, utilization, active_status
            ]

        # Combina e mescola
        X = np.vstack([X_normal, X_anomaly])

        # Se ci sono dati reali (extra_data), vengono aggiunti al training set
        if extra_data:
            real_data_array = np.array(extra_data)
            logger.info(f"-> Injecting {len(real_data_array)} REAL traffic samples into training set")
            X = np.vstack([X, real_data_array])

        np.random.shuffle(X)

        # Scala i dati
        X_scaled = self.scaler.fit_transform(X)

        # Addestra Isolation Forest con contamination realistica
        contamination = 0.15  # 15% anomalie attese
        self.model = IsolationForest(
            n_estimators=150,
            contamination=contamination,
            random_state=42,
            max_samples='auto',
            max_features=0.8,
            bootstrap=False
        )

        self.model.fit(X_scaled)
        self.is_trained = True

        # Salva modello
        self._save_model()

        # Valuta modello
        predictions = self.model.predict(X_scaled)
        n_anomalies = sum(predictions == -1)
        expected_anomalies = int(n_samples * contamination)

        logger.info(f"Model trained with {len(X)} samples")
        logger.info(f"Detected {n_anomalies} anomalies in training (expected: {expected_anomalies})")
        logger.info(f"Training accuracy: {abs(n_anomalies - expected_anomalies) / expected_anomalies:.1%} error")

    def _save_model(self):
        # Salva modello e scaler
        try:
            with open(self.model_file, 'wb') as f:
                pickle.dump(self.model, f)

            with open(self.scaler_file, 'wb') as f:
                pickle.dump(self.scaler, f)

            logger.debug(f"Model saved to {self.model_file}")
        except Exception as e:
            logger.error(f"Error saving model: {e}")

    def _load_model(self):
        # Carica modello e scaler
        try:
            with open(self.model_file, 'rb') as f:
                self.model = pickle.load(f)

            with open(self.scaler_file, 'rb') as f:
                self.scaler = pickle.load(f)

            self.is_trained = True
            logger.info(f"📂 Model loaded from {self.model_file}")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            self._train_model()

    def _model_files_exist(self):
        # Verifica se i file del modello esistono
        return os.path.exists(self.model_file) and os.path.exists(self.scaler_file)

    def detect_anomalies(self, features_data):
        # Rileva anomalie nei dati
        if not features_data:
            return []

        anomalies = []

        for item in features_data:
            resource_id = item['resource_id']
            resource_name = item['resource_name']
            features = item['features']
            raw_metrics = item.get('raw_metrics', {})
            source = item.get('source', 'unknown')

            # salva soltanto se il traffico non è generato
            if 'generated' not in source:
                self.real_traffic_history.append(features)
                logger.info(f"🔎 PORTA REALE: {resource_name} | PKT_IN: {features[2]} | PKT_OUT: {features[3]}")

                # Controllo se dobbiamo ri-addestrare
                if len(self.real_traffic_history) % self.retrain_threshold == 0:
                    logger.info("Knowledge Threshold reached. Updating AI model...")
                    self._retrain_incremental()

            self.detection_stats['total_checked'] += 1

            # DEBUG per campioni generati
            is_generated = 'generated' in source
            if is_generated and self.config.get('debug', False):
                generated_type = raw_metrics.get('generated_type', 'unknown')
                logger.debug(f"🔍 Checking generated sample: {resource_name} ({generated_type})")

            # Controllo soglie per evitare falsi positivi
            threshold_anomaly, triggered_thresholds = self._check_thresholds(features, resource_name)

            # Rilevamento ML
            ml_anomaly = False
            ml_score = 0.0
            ml_confidence = 0.0

            if self.is_trained:
                ml_result = self._detect_with_ml(features)
                ml_anomaly = ml_result['is_anomaly']
                ml_score = ml_result['score']
                ml_confidence = ml_result['confidence']

            # Decisione finale
            is_anomaly = False
            detection_method = 'none'
            anomaly_score = 0.0

            if threshold_anomaly:
                # Se supera le soglie anomalia certa
                is_anomaly = True
                detection_method = 'threshold'
                anomaly_score = 0.85  # Alta confidenza
                self.detection_stats['threshold_anomalies'] += 1

                logger.debug(f"📊 Threshold anomaly confirmed: {resource_name}")
                logger.debug(f"   Triggered: {triggered_thresholds}")

            elif ml_anomaly and ml_confidence > 0.7:
                # Se ML rileva con alta confidenza anomalia probabile
                is_anomaly = True
                detection_method = 'isolation_forest'
                anomaly_score = ml_confidence
                self.detection_stats['ml_anomalies'] += 1

                # Verifica che non sia un falso positivo su traffico normale generato
                if is_generated and raw_metrics.get('generated_type') == 'normal':
                    # Controllo aggiuntivo per traffico normale generato
                    if ml_confidence < 0.85:  # Se confidenza non molto alta
                        logger.debug(
                            f"ML flagged normal generated traffic: {resource_name} (confidence: {ml_confidence:.2f})")
                        # Considera come possibile falso positivo
                        self.detection_stats['false_positives'] += 1

            if is_anomaly:
                # Determina tipo di anomalia
                if threshold_anomaly:
                    anomaly_type = self._determine_threshold_anomaly(features, triggered_thresholds)
                else:
                    anomaly_type = self._determine_ml_anomaly_type(features, ml_score, ml_confidence)

                # Crea dizionario anomalia
                anomaly = {
                    'resource_id': resource_id,
                    'resource_type': item['resource_type'],
                    'resource_name': resource_name,
                    'anomaly_type': anomaly_type,
                    'anomaly_score': anomaly_score,
                    'detection_method': detection_method,
                    'features': {
                        'bytes_in_kb': features[0],
                        'bytes_out_kb': features[1],
                        'packets_in': features[2],
                        'packets_out': features[3],
                        'drop_rate': features[4],
                        'num_ports': features[5],
                        'utilization': features[6],
                        'active_status': features[7]
                    },
                    'raw_metrics': raw_metrics,
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': source,
                    'ml_confidence': ml_confidence,
                    'threshold_triggered': threshold_anomaly,
                    'triggered_thresholds': triggered_thresholds if threshold_anomaly else []
                }

                anomalies.append(anomaly)

                # Log dettagliato
                source_label = "SIMULATED" if is_generated else "REAL_TRAFFIC"
                logger.warning(f"----------ANOMALY DETECTED [{source_label}]: {resource_name}----------")
                # Dettagli
                logger.info(f"    Type: {anomaly_type}")
                logger.info(f"    Severity Score: {anomaly_score:.2f}")
                logger.info(f"    Method: {detection_method}")

                if threshold_anomaly and triggered_thresholds:
                    logger.info(f"   Thresholds: {', '.join(triggered_thresholds[:2])}")

                if is_generated:
                    generated_type = raw_metrics.get('generated_type', 'unknown')
                    logger.info(f"[SIMULATED] Generated type: {generated_type}")
                    if generated_type == 'normal' and detection_method == 'isolation_forest':
                        logger.info(f"Possible false positive on normal traffic")

        # Log statistiche periodiche
        if self.detection_stats['total_checked'] % 20 == 0:
            self._log_detection_stats()

        return anomalies

    def _check_thresholds(self, features, resource_name):
        # Controlla se le feature superano le soglie
        try:
            triggered = []

            # Controlla ogni soglia
            checks = [
                (features[0] > self.adjusted_thresholds['bytes_in_kb'],
                 f"bytes_in={features[0]:.0f}KB > {self.adjusted_thresholds['bytes_in_kb']:.0f}KB"),
                (features[1] > self.adjusted_thresholds['bytes_out_kb'],
                 f"bytes_out={features[1]:.0f}KB > {self.adjusted_thresholds['bytes_out_kb']:.0f}KB"),
                (features[2] > self.adjusted_thresholds['packets_in'],
                 f"packets_in={features[2]:.0f} > {self.adjusted_thresholds['packets_in']:.0f}"),
                (features[3] > self.adjusted_thresholds['packets_out'],
                 f"packets_out={features[3]:.0f} > {self.adjusted_thresholds['packets_out']:.0f}"),
                (features[4] > self.adjusted_thresholds['drop_rate'],
                 f"drop_rate={features[4]:.2%} > {self.adjusted_thresholds['drop_rate']:.1%}"),
                (features[5] > self.adjusted_thresholds['num_ports'],
                 f"num_ports={features[5]:.0f} > {self.adjusted_thresholds['num_ports']:.0f}"),
                (features[6] > self.adjusted_thresholds['utilization'],
                 f"utilization={features[6]:.1%} > {self.adjusted_thresholds['utilization']:.1%}"),
                (features[7] < self.adjusted_thresholds['active_status'],
                 f"active={features[7]:.1f} < {self.adjusted_thresholds['active_status']:.1f}")
            ]

            for check_passed, message in checks:
                if check_passed:
                    triggered.append(message)

            return len(triggered) > 0, triggered

        except Exception as e:
            logger.error(f"Error in threshold check for {resource_name}: {e}")
            return False, []

    def _determine_threshold_anomaly(self, features, triggered_thresholds):
        # Determina il tipo di anomalia
        # Ordina per gravità percepita
        if any("drop_rate" in t for t in triggered_thresholds):
            return 'HIGH_DROP_RATE'
        elif any("bytes_in" in t for t in triggered_thresholds):
            return 'HIGH_TRAFFIC_IN'
        elif any("bytes_out" in t for t in triggered_thresholds):
            return 'HIGH_TRAFFIC_OUT'
        elif any("packets_in" in t for t in triggered_thresholds):
            return 'HIGH_PACKET_RATE_IN'
        elif any("packets_out" in t for t in triggered_thresholds):
            return 'HIGH_PACKET_RATE_OUT'
        elif any("num_ports" in t for t in triggered_thresholds):
            return 'TOO_MANY_PORTS'
        elif any("utilization" in t for t in triggered_thresholds):
            return 'HIGH_UTILIZATION'
        elif any("active" in t for t in triggered_thresholds):
            return 'RESOURCE_DOWN'
        else:
            return 'THRESHOLD_ANOMALY'

    def _determine_ml_anomaly_type(self, features, ml_score, ml_confidence):
        # Determina tipo di anomalia per ML detection
        if ml_confidence > 0.9:
            return 'STRONG_ML_ANOMALY'
        elif ml_confidence > 0.8:
            # Cerca di capire il tipo in base alle features
            if features[4] > 0.05:  # drop rate alto
                return 'SUSPICIOUS_DROP_RATE_ML'
            elif features[0] > 8000 or features[1] > 6000:  # traffico alto
                return 'ELEVATED_TRAFFIC_ML'
            elif features[5] > 20:  # molte porte
                return 'SUSPICIOUS_PORT_COUNT_ML'
            else:
                return 'MODERATE_ML_ANOMALY'
        else:
            return 'WEAK_ML_ANOMALY'

    def _detect_with_ml(self, features):
        # Rileva anomalie usando Isolation Forest con confidenza calibrata
        try:
            # Prepara features per il modello
            X = np.array(features).reshape(1, -1)
            X_scaled = self.scaler.transform(X)

            # Predizione
            prediction = self.model.predict(X_scaled)
            decision_score = self.model.decision_function(X_scaled)[0]

            # Calcola confidenza (0-1)
            # Isolation Forest: decision_score < 0 = anomalia
            # Più negativo = più anomalo
            if decision_score < 0:
                # Normalizza a [0.5, 1.0]
                # decision_score tipico range: [-0.5, 0.5] per anomalie
                confidence = 0.5 + min(abs(decision_score), 0.5)
            else:
                # Non anomalia
                confidence = 0.5 - min(decision_score, 0.5)

            is_anomaly = prediction[0] == -1

            return {
                'is_anomaly': is_anomaly,
                'score': float(decision_score),
                'confidence': float(confidence)
            }

        except Exception as e:
            logger.error(f"ML detection error: {e}")
            return {'is_anomaly': False, 'score': 0.0, 'confidence': 0.0}

    def _log_detection_stats(self):
        # Log delle statistiche di detection
        total = self.detection_stats['total_checked']
        if total == 0:
            return

        threshold_rate = self.detection_stats['threshold_anomalies'] / total
        ml_rate = self.detection_stats['ml_anomalies'] / total
        fp_rate = self.detection_stats['false_positives'] / max(1, self.detection_stats['ml_anomalies'])

        logger.info(f"   Detection stats after {total} samples:")
        logger.info(f"   Threshold anomalies: {self.detection_stats['threshold_anomalies']} ({threshold_rate:.1%})")
        logger.info(f"   ML anomalies: {self.detection_stats['ml_anomalies']} ({ml_rate:.1%})")
        if self.detection_stats['false_positives'] > 0:
            logger.info(f"   Possible false positives: {self.detection_stats['false_positives']} ({fp_rate:.1%} of ML)")

    def get_detection_stats(self):
        # Restituisce statistiche complete del detector
        stats = {
            'base_thresholds': self.base_thresholds,
            'adjusted_thresholds': self.adjusted_thresholds,
            'model_trained': self.is_trained,
            'model_type': 'IsolationForest',
            'features_count': 8,
            'detection_stats': self.detection_stats.copy()
        }

        if self.is_trained and self.model:
            stats.update({
                'contamination': self.model.contamination,
                'n_estimators': self.model.n_estimators,
                'model_file': self.model_file
            })

        # Calcola rates
        total = self.detection_stats['total_checked']
        if total > 0:
            stats['detection_stats']['threshold_rate'] = self.detection_stats['threshold_anomalies'] / total
            stats['detection_stats']['ml_rate'] = self.detection_stats['ml_anomalies'] / total
            stats['detection_stats']['total_anomaly_rate'] = (
                                                                     self.detection_stats['threshold_anomalies'] +
                                                                     self.detection_stats['ml_anomalies']
                                                             ) / total

        return stats

    def update_thresholds(self, new_thresholds):
        # Aggiorna le soglie di detection
        self.base_thresholds.update(new_thresholds)
        self.adjusted_thresholds = self._calculate_adjusted_thresholds()
        logger.info(f"   Detection thresholds updated")
        logger.info(f"   New base thresholds: {self.base_thresholds}")
        logger.info(f"   New adjusted thresholds: {self.adjusted_thresholds}")

    def reset_stats(self):
        # Resetta le statistiche di detection
        self.detection_stats = {
            'total_checked': 0,
            'threshold_anomalies': 0,
            'ml_anomalies': 0,
            'false_positives': 0
        }
        logger.info("Detection statistics reset")