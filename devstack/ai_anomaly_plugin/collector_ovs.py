import logging
import warnings
import subprocess
import re
from datetime import datetime
import numpy as np
import random

# Ignora warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    import openstack
    OPENSTACK_AVAILABLE = True
except ImportError:
    OPENSTACK_AVAILABLE = False
    logging.error("OpenStack SDK not available. Install with: pip install openstacksdk")

logger = logging.getLogger(__name__)


class TrafficGenerator:
    #Generatore di traffico OVS per simulare traffico normale o anomalo

    def __init__(self, config=None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.min_samples = self.config.get('min_samples', 2)  # Minimo campioni per ciclo
        self.max_samples = self.config.get('max_samples', 8)  # Massimo campioni per ciclo
        self.anomaly_ratio = self.config.get('anomaly_ratio', 0.4)

        # Probabilità di avere 0 metriche reali (simula OVS down)
        self.zero_real_prob = self.config.get('zero_real_prob', 0.1)  # 10%

        # Soglie per anomalie
        self.thresholds = {
            'bytes_in_kb': 5000.0,
            'bytes_out_kb': 4000.0,
            'packets_in': 10000.0,
            'packets_out': 8000.0,
            'drop_rate': 0.02,
            'num_ports': 25.0,
            'utilization': 0.8,
            'active_status': 0.5
        }

        # Bridge realistici
        self.bridges = ['br-int', 'br-ex', 'br-tun', 'br-data'] #integration-bridge, external bridge,

        # Tipi di porte con probabilità di apparizione
        self.port_types = [
            ('tap', 0.4),     # 40% VM ports
            ('vnet', 0.3),    # 30% VM ports
            ('qr-', 0.1),     # 10% router
            ('qg-', 0.1),     # 10% router
            ('patch-', 0.05), # 5% patch
            ('phy-', 0.05)    # 5% physical
        ]

        # Porte persistenti simulano porte che rimangono tra i cicli
        self.persistent_ports = {}
        self.next_port_id = 1000

        # Statistiche
        self.stats = {
            'total_generated': 0,
            'anomalies_generated': 0,
            'normal_generated': 0,
            'cycles_with_zero_real': 0
        }

        if self.enabled:
            logger.info(f"->Traffic Generator enabled<-")
            logger.info(f"Samples: {self.min_samples}-{self.max_samples}/cycle")
            logger.info(f"Anomaly ratio: {self.anomaly_ratio*100}%")
            logger.info(f"Zero real prob: {self.zero_real_prob*100}%")

    def _select_port_type(self):
        #Seleziona tipo di porta in base alle probabilità
        types, probs = zip(*self.port_types)
        return np.random.choice(types, p=probs)

    def generate_port_name(self, port_type, is_anomaly=False, make_persistent=False):
        #Genera un nome porta realistico
        if make_persistent and self.next_port_id in self.persistent_ports:
            # Usa porta persistente esistente
            return self.persistent_ports[self.next_port_id]

        if port_type in ['tap', 'vnet']:
            # Porte VM
            port_num = self.next_port_id
            port_id = f"{port_type}{port_num:04d}"
        elif port_type in ['qr-', 'qg-']:
            # Porte router
            port_num = np.random.randint(1, 99)
            port_id = f"{port_type}{port_num:02d}"
        else:
            # Altre porte
            port_num = np.random.randint(1, 999)
            port_id = f"{port_type}{port_num}"

        if is_anomaly and np.random.random() < 0.3:
            # Aggiungi suffix sospetto per anomalie
            suffix = np.random.choice(['_flood', '_scan', '_ddos', '_mal', '_brute'])
            port_id += suffix

        # Memorizza se persistente
        if make_persistent:
            self.persistent_ports[self.next_port_id] = port_id
            self.next_port_id += 1

        return port_id

    def generate_normal_traffic(self, make_persistent=False):
        #Genera traffico NORMALE
        port_type = self._select_port_type()
        is_persistent = make_persistent and np.random.random() < 0.3

        port_name = self.generate_port_name(port_type, is_anomaly=False,
                                            make_persistent=is_persistent)
        bridge = np.random.choice(self.bridges)

        # Simula variazioni realistiche
        hour = datetime.now().hour

        # Pattern di traffico realistico in base alle ore della giornata

        if 0 <= hour < 6:
            time_factor = 0.3
        elif 6 <= hour < 9:
            time_factor = 0.7
        elif 9 <= hour < 18:
            time_factor = 1.5
        else:
            time_factor = 0.9

        # Traffico inbound KB
        base_traffic = np.random.exponential(scale=300)  # Media 300KB

        # Aggiunta rumore
        noise = np.random.uniform(0.8, 1.2)
        bytes_in_kb = base_traffic * time_factor * noise

        # Assicura che sia SOTTO le soglie
        bytes_in_kb = min(bytes_in_kb, self.thresholds['bytes_in_kb'] * 0.4)  # 40% della soglia

        # Traffico outbound
        outbound_ratio = np.random.uniform(0.6, 0.9)
        bytes_out_kb = bytes_in_kb * outbound_ratio
        bytes_out_kb = min(bytes_out_kb, self.thresholds['bytes_out_kb'] * 0.4)

        # Pacchetti realistici
        avg_packet_size = np.random.uniform(500, 1500)
        packets_in = int(bytes_in_kb * 1024 / avg_packet_size)
        packets_out = int(bytes_out_kb * 1024 / avg_packet_size)

        # Assicura pacchetti sotto le soglie
        packets_in = min(packets_in, self.thresholds['packets_in'] * 0.3)
        packets_out = min(packets_out, self.thresholds['packets_out'] * 0.3)

        # Drop rate basso per traffico normale
        drop_rate = np.random.beta(1, np.random.randint(1000, 5000))

        # Altre feature realistiche
        num_ports = np.random.randint(2, 12)  # Meno porte
        utilization = np.random.beta(2, 8)  # Media 20% utilizzo
        active_status = 1.0 if np.random.random() > 0.02 else 0.0  # 98% attivo

        features = [
            float(bytes_in_kb),
            float(bytes_out_kb),
            float(packets_in),
            float(packets_out),
            float(drop_rate),
            float(num_ports),
            float(utilization),
            float(active_status)
        ]

        return port_name, bridge, features

    def generate_anomalous_traffic(self, make_persistent=False):
        #Genera traffico anomalo
        port_type = self._select_port_type()
        is_persistent = make_persistent and np.random.random() < 0.5

        port_name = self.generate_port_name(port_type, is_anomaly=True,
                                            make_persistent=is_persistent)
        bridge = np.random.choice(self.bridges)

        # Scegli tipo di anomalia
        anomaly_types = [
            ('HIGH_TRAFFIC', 0.30),  # 30% traffico
            ('HIGH_DROP_RATE', 0.30),  # 30% drop rate
            ('RESOURCE_DOWN', 0.15),  # 15% porta down
            ('HIGH_PACKET_RATE', 0.15),  # 15% pacchetti
            ('TOO_MANY_PORTS', 0.10)  # 10% troppe porte
        ]

        anomaly_names, anomaly_probs = zip(*anomaly_types)
        anomaly_type = np.random.choice(anomaly_names, p=anomaly_probs)

        # DEBUG: Forza alcuni tipi di anomalie per test
        if np.random.random() < 0.3:  # 30% probabilità di forzare HIGH_DROP_RATE
            anomaly_type = 'HIGH_DROP_RATE'

        # Genera features che superano le soglie
        if anomaly_type == 'HIGH_TRAFFIC':
            # Traffico alto
            multiplier = np.random.uniform(3.0, 8.0) #moltiplicatore di intensità
            bytes_in_kb = self.thresholds['bytes_in_kb'] * multiplier #byte in input
            bytes_out_kb = self.thresholds['bytes_out_kb'] * multiplier * 0.8 #byte in output
            packets_in = int(bytes_in_kb * 1024 / np.random.uniform(800, 1200)) #pacchetti in input
            packets_out = int(bytes_out_kb * 1024 / np.random.uniform(800, 1200)) #pacchetti in output
            drop_rate = np.random.beta(1, 300)  # 0.33% medio
            num_ports = np.random.randint(5, 15)
            utilization = np.random.uniform(0.85, 0.95)
            active_status = 1.0

        elif anomaly_type == 'HIGH_DROP_RATE':
            # Drop rate alto con traffico medio
            bytes_in_kb = np.random.exponential(scale=300)
            bytes_out_kb = bytes_in_kb * np.random.uniform(0.7, 0.9)
            packets_in = int(bytes_in_kb * 1024 / np.random.uniform(800, 1200))
            packets_out = int(bytes_out_kb * 1024 / np.random.uniform(800, 1200))
            drop_rate = np.random.uniform(0.20, 0.60)  # 20-60% drop rate!
            num_ports = np.random.randint(3, 12)
            utilization = np.random.beta(2, 4)
            active_status = 1.0

        elif anomaly_type == 'RESOURCE_DOWN':
            # Porta completamente down
            bytes_in_kb = 0
            bytes_out_kb = 0
            packets_in = 0
            packets_out = 0
            drop_rate = 0
            num_ports = np.random.randint(1, 4)
            utilization = 0
            active_status = 0.0

        elif anomaly_type == 'HIGH_PACKET_RATE':
            # Attacco DDoS
            bytes_in_kb = np.random.exponential(scale=50)  # pochi byte
            bytes_out_kb = np.random.exponential(scale=40)
            packet_multiplier = np.random.uniform(3.0, 6.0)
            packets_in = self.thresholds['packets_in'] * packet_multiplier
            packets_out = self.thresholds['packets_out'] * packet_multiplier * 0.9
            drop_rate = np.random.uniform(0.10, 0.30)  # 10-30% drop
            num_ports = np.random.randint(2, 8)
            utilization = np.random.uniform(0.6, 0.8)
            active_status = 1.0

        else:  # TOO_MANY_PORTS
            # Molte porte
            bytes_in_kb = np.random.exponential(scale=500)
            bytes_out_kb = bytes_in_kb * np.random.uniform(0.7, 0.9)
            packets_in = int(bytes_in_kb * 1024 / np.random.uniform(800, 1200))
            packets_out = int(bytes_out_kb * 1024 / np.random.uniform(800, 1200))
            drop_rate = np.random.beta(1, 200)
            port_multiplier = np.random.uniform(2.0, 4.0)
            num_ports = int(self.thresholds['num_ports'] * port_multiplier)
            utilization = np.random.beta(3, 4)
            active_status = 1.0

        features = [
            float(bytes_in_kb),
            float(bytes_out_kb),
            float(packets_in),
            float(packets_out),
            float(drop_rate),
            float(num_ports),
            float(utilization),
            float(active_status)
        ]

        # LOG per debug
        logger.debug(f"->Generated STRONG anomaly: {port_name} - {anomaly_type}<-")
        logger.debug(f"   Features: bytes_in={bytes_in_kb:.0f}KB, drop={drop_rate:.1%}, "
                     f"ports={num_ports}, active={active_status}")

        return port_name, bridge, features, anomaly_type

    def generate_samples(self, real_sample_count, cycle_num):
        #Genera campioni di traffico variabile
        if not self.enabled:
            return []

        # A volte simula 0 metriche reali (OVS down o nessun traffico)
        simulate_zero_real = np.random.random() < self.zero_real_prob
        if simulate_zero_real:
            real_sample_count = 0
            self.stats['cycles_with_zero_real'] += 1
            logger.info(f"-Simulating zero real metrics (OVS down scenario)-")

        # Numero variabile di campioni generati
        if real_sample_count == 0:
            # Se 0 reali, genera un po' più di campioni
            num_to_generate = np.random.randint(self.min_samples, self.max_samples + 2)
        else:
            # Altrimenti varia tra min e max
            num_to_generate = np.random.randint(self.min_samples, self.max_samples + 1)

        # Ogni 5 cicli, aggiungi un "burst" di traffico
        if cycle_num % 5 == 0:
            num_to_generate = min(num_to_generate * 2, self.max_samples * 2)
            logger.info(f"Burst cycle: generating {num_to_generate} samples")

        generated_samples = []
        persistent_this_cycle = cycle_num % 3 == 0  # Ogni 3 cicli alcune porte persistenti

        for i in range(num_to_generate):
            # Decide se generare anomalia
            is_anomaly = np.random.random() < self.anomaly_ratio

            # Decide se questa porta è persistente
            make_persistent = persistent_this_cycle and np.random.random() < 0.4

            if is_anomaly:
                port_name, bridge, features, anomaly_type = self.generate_anomalous_traffic(
                    make_persistent=make_persistent
                )
                source = 'generated_anomaly'
                self.stats['anomalies_generated'] += 1
            else:
                port_name, bridge, features = self.generate_normal_traffic(
                    make_persistent=make_persistent
                )
                anomaly_type = None
                source = 'generated_normal'
                self.stats['normal_generated'] += 1

            sample = {
                'resource_id': port_name,
                'resource_type': 'ovs_port',
                'resource_name': f"{bridge}:{port_name}",
                'features': features,
                'raw_metrics': {
                    'bridge': bridge,
                    'port': port_name,
                    'rx_bytes': int(features[0] * 1024),
                    'tx_bytes': int(features[1] * 1024),
                    'rx_packets': int(features[2]),
                    'tx_packets': int(features[3]),
                    'rx_dropped': int(features[2] * features[4]),
                    'tx_dropped': int(features[3] * features[4]),
                    'total_bytes': int((features[0] + features[1]) * 1024),
                    'drop_rate': features[4],
                    'timestamp': datetime.utcnow().isoformat(),
                    'is_generated': True,
                    'generated_type': 'anomaly' if is_anomaly else 'normal',
                    'anomaly_type': anomaly_type,
                    'is_persistent': make_persistent
                },
                'source': source
            }

            generated_samples.append(sample)
            self.stats['total_generated'] += 1

        return generated_samples

    def get_stats(self):
        #Restituisce statistiche del generatore
        stats = self.stats.copy()
        stats['enabled'] = self.enabled
        stats['min_samples'] = self.min_samples
        stats['max_samples'] = self.max_samples
        stats['anomaly_ratio'] = self.anomaly_ratio
        stats['zero_real_prob'] = self.zero_real_prob
        stats['persistent_ports_count'] = len(self.persistent_ports)

        if stats['total_generated'] > 0:
            stats['anomaly_rate'] = stats['anomalies_generated'] / stats['total_generated']
        else:
            stats['anomaly_rate'] = 0.0

        return stats


class OVSRealMetricsCollector:
    #Collector per metriche REALI da Open vSwitch

    def __init__(self, debug=False):
        self.debug = debug
        logger.info("->OVS Real Metrics Collector initialized<-")
        self.previous_stats = {}

    def _run_command(self, command, timeout=5):
        #Esegue comando shell
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                executable='/bin/bash'
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception as e:
            if self.debug:
                logger.debug(f"Command error: {e}")
            return None

    def get_ovs_bridges(self):
        #Ottiene tutti i bridge OVS
        output = self._run_command("sudo ovs-vsctl list-br")
        if output:
            bridges = [b.strip() for b in output.split('\n') if b.strip()]
            return bridges
        return ['br-int', 'br-ex']

    def get_bridge_ports(self, bridge_name):
        #Ottiene tutte le porte di un bridge
        output = self._run_command(f"sudo ovs-vsctl list-ports {bridge_name}")
        if output:
            return [p.strip() for p in output.split('\n') if p.strip()]
        return []

    def get_port_statistics(self, bridge_name, port_name):
        #Ottiene statistiche di una porta OVS
        stats = {
            'rx_packets': 0, 'tx_packets': 0,
            'rx_bytes': 0, 'tx_bytes': 0,
            'rx_dropped': 0, 'tx_dropped': 0,
            'rx_errors': 0, 'tx_errors': 0
        }

        # Metodo 1: ovs-vsctl
        cmd = f"sudo ovs-vsctl get Interface {port_name} statistics"
        output = self._run_command(cmd)

        if output and output != '{}':
            clean_output = output.strip('{} ')
            if clean_output:
                pairs = [p.strip() for p in re.split(r',\s*', clean_output)]
                for pair in pairs:
                    if '=' in pair:
                        try:
                            key, value = pair.split('=', 1)
                            key, value = key.strip(), value.strip()

                            if key == 'rx_packets':
                                stats['rx_packets'] = int(value)
                            elif key == 'tx_packets':
                                stats['tx_packets'] = int(value)
                            elif key == 'rx_bytes':
                                stats['rx_bytes'] = int(value)
                            elif key == 'tx_bytes':
                                stats['tx_bytes'] = int(value)
                            elif key == 'rx_dropped':
                                stats['rx_dropped'] = int(value)
                            elif key == 'tx_dropped':
                                stats['tx_dropped'] = int(value)
                            elif key == 'rx_errors':
                                stats['rx_errors'] = int(value)
                            elif key == 'tx_errors':
                                stats['tx_errors'] = int(value)
                        except (ValueError, TypeError):
                            continue

        # Metodo 2: ovs-ofctl (fallback)
        if stats['rx_bytes'] == 0 and stats['tx_bytes'] == 0:
            cmd = f"sudo ovs-ofctl dump-ports {bridge_name} {port_name} 2>/dev/null || true"
            of_output = self._run_command(cmd)

            if of_output:
                rx_match = re.search(r'rx pkts=(\d+),\s*bytes=(\d+),\s*drop=(\d+)', of_output)
                if rx_match:
                    stats['rx_packets'] = int(rx_match.group(1))
                    stats['rx_bytes'] = int(rx_match.group(2))
                    stats['rx_dropped'] = int(rx_match.group(3))

                tx_match = re.search(r'tx pkts=(\d+),\s*bytes=(\d+),\s*drop=(\d+)', of_output)
                if tx_match:
                    stats['tx_packets'] = int(tx_match.group(1))
                    stats['tx_bytes'] = int(tx_match.group(2))
                    stats['tx_dropped'] = int(tx_match.group(3))

        return stats

    def collect_all_ovs_metrics(self):
        #Raccoglie tutte le metriche REALI da OVS
        logger.info("Collecting REAL traffic metrics from OVS...")

        all_metrics = []
        bridges = self.get_ovs_bridges()

        if not bridges:
            logger.warning("No OVS bridges found")
            return all_metrics

        for bridge in bridges:
            try:
                ports = self.get_bridge_ports(bridge)
                if not ports:
                    continue

                for port in ports:
                    try:
                        stats = self.get_port_statistics(bridge, port)

                        total_packets = stats['rx_packets'] + stats['tx_packets']
                        total_dropped = stats['rx_dropped'] + stats['tx_dropped']
                        total_bytes = stats['rx_bytes'] + stats['tx_bytes']

                        drop_rate = total_dropped / total_packets if total_packets > 0 else 0.0

                        port_metrics = {
                            'resource_id': port,
                            'resource_type': 'ovs_port',
                            'resource_name': f"{bridge}:{port}",
                            'bridge': bridge,
                            'port': port,
                            'rx_bytes': stats['rx_bytes'],
                            'tx_bytes': stats['tx_bytes'],
                            'rx_packets': stats['rx_packets'],
                            'tx_packets': stats['tx_packets'],
                            'rx_dropped': stats['rx_dropped'],
                            'tx_dropped': stats['tx_dropped'],
                            'total_bytes': total_bytes,
                            'drop_rate': drop_rate,
                            'has_traffic': total_bytes > 0,
                            'timestamp': datetime.utcnow().isoformat()
                        }

                        all_metrics.append(port_metrics)

                        if self.debug and total_bytes > 0:
                            logger.debug(f"  Port {port}: RX={stats['rx_bytes']/1024:.1f}KB, "
                                       f"TX={stats['tx_bytes']/1024:.1f}KB, "
                                       f"Drop={drop_rate*100:.2f}%")
                    except Exception as e:
                        if self.debug:
                            logger.debug(f"Failed to get stats for port {port}: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Failed to process bridge {bridge}: {e}")
                continue

        active_ports = [m for m in all_metrics if m['has_traffic']]
        logger.info(f"✅ Collected REAL metrics from {len(all_metrics)} OVS ports "
                  f"({len(active_ports)} with traffic)")

        return all_metrics


class NeutronOVSCollector:
    #Collector ibrido: combina dati reali OVS con traffico generato

    def __init__(self, config):
        if not OPENSTACK_AVAILABLE:
            raise ImportError("OpenStack SDK not available")

        self.config = config
        self.conn = self._get_openstack_connection()

        debug_mode = config.get('ovs', {}).get('debug', False)
        self.ovs_collector = OVSRealMetricsCollector(debug=debug_mode)

        # Inizializza generatore
        generator_config = config.get('generator', {})
        self.traffic_generator = TrafficGenerator(generator_config)

        # Contatore cicli
        self.cycle_count = 0

        logger.info("Connected to OpenStack + OVS Real Metrics + Traffic Generator")

    def _get_openstack_connection(self):
        #Crea connessione OpenStack
        auth_config = self.config['openstack']
        return openstack.connect(
            auth_url=auth_config['auth_url'],
            project_name=auth_config['project_name'],
            username=auth_config['username'],
            password=auth_config['password'],
            user_domain_name=auth_config['user_domain'],
            project_domain_name=auth_config['project_domain']
        )

    def collect_metrics(self):
        #Raccoglie metriche ibride
        self.cycle_count += 1

        try:
            logger.info(f"Collecting hybrid network metrics (cycle #{self.cycle_count})...")

            # Ottieni metriche REALI da OVS (a volte può essere 0!)
            ovs_metrics = self.ovs_collector.collect_all_ovs_metrics()
            real_features = []

            if ovs_metrics:
                # Filtra solo porte con traffico
                ovs_metrics = [m for m in ovs_metrics if m['has_traffic']]

                if ovs_metrics:
                    real_features = self._prepare_ovs_features(ovs_metrics)
                    logger.info(f"✅ Collected {len(real_features)} REAL OVS metrics")
                else:
                    logger.info("✅ No traffic on real OVS ports")
            else:
                logger.info("⚠️ No real OVS metrics collected")

            # Se nessuna metrica reale, a volte usa stime Neutron
            if not real_features and np.random.random() < 0.3:  # 30% probabilità
                logger.warning("Using Neutron estimates as fallback")
                real_features = self._collect_neutron_estimates()

            # Genera e inietta traffico VARIABILE
            if self.traffic_generator.enabled:
                generated_samples = self.traffic_generator.generate_samples(
                    len(real_features),
                    self.cycle_count
                )

                if generated_samples:
                    # Combina e mescola
                    all_samples = real_features + generated_samples
                    np.random.shuffle(all_samples)

                    # Analizza composizione
                    anomalies_injected = len([s for s in generated_samples
                                            if s['source'] == 'generated_anomaly'])
                    persistent_count = len([s for s in generated_samples
                                          if s['raw_metrics'].get('is_persistent', False)])

                    logger.info(f"->Generated {len(generated_samples)} samples<-")
                    logger.info(f"   Anomalies: {anomalies_injected}")
                    logger.info(f"   Persistent ports: {persistent_count}")
                    logger.info(f"   Total samples: {len(all_samples)}")

                    return all_samples

            return real_features

        except Exception as e:
            logger.error(f"Collection error: {e}")
            return self._get_fallback_metrics()

    def _prepare_ovs_features(self, ovs_metrics):
        #Prepara features per ML dalle metriche OVS
        features = []

        for metric in ovs_metrics:
            # Converti bytes in KB
            bytes_in_kb = metric['rx_bytes'] / 1024
            bytes_out_kb = metric['tx_bytes'] / 1024

            # Pacchetti
            packets_in = metric['rx_packets']
            packets_out = metric['tx_packets']

            # Drop rate
            drop_rate = min(1.0, metric.get('drop_rate', 0))

            # Altre feature simulate per compatibilità
            num_ports = np.random.randint(3, 15)  # Simulato
            utilization = min(1.0, (bytes_in_kb + bytes_out_kb) / (100 * 1024))  # Rispetto a 100MB
            active_status = 1.0 if metric['has_traffic'] else 0.0

            feature_vector = [
                float(bytes_in_kb),
                float(bytes_out_kb),
                float(packets_in),
                float(packets_out),
                float(drop_rate),
                float(num_ports),
                float(utilization),
                float(active_status)
            ]

            features.append({
                'resource_id': metric['resource_id'],
                'resource_type': metric['resource_type'],
                'resource_name': metric['resource_name'],
                'features': feature_vector,
                'raw_metrics': metric,
                'source': 'ovs_real'
            })

        return features

    def _collect_neutron_estimates(self):
        #Stime basate su risorse Neutron
        try:
            routers = list(self.conn.network.routers())
            features = []

            for router in routers[:3]:  # Limita a 3 router
                status = 1 if router.status == 'ACTIVE' else 0

                # Stime conservative
                bytes_in_kb = np.random.exponential(scale=500)
                bytes_out_kb = bytes_in_kb * np.random.uniform(0.7, 0.9)
                packets_in = int(bytes_in_kb * 1024 / np.random.uniform(800, 1200))
                packets_out = int(bytes_out_kb * 1024 / np.random.uniform(800, 1200))
                drop_rate = np.random.beta(1, 500)
                num_ports = np.random.randint(2, 8)
                utilization = np.random.beta(2, 5)

                feature_vector = [
                    float(bytes_in_kb),
                    float(bytes_out_kb),
                    float(packets_in),
                    float(packets_out),
                    float(drop_rate),
                    float(num_ports),
                    float(utilization),
                    float(status)
                ]

                features.append({
                    'resource_id': router.id,
                    'resource_type': 'router',
                    'resource_name': router.name or router.id[:8],
                    'features': feature_vector,
                    'raw_metrics': {'status': router.status},
                    'source': 'neutron_estimate'
                })

            logger.info(f"Generated {len(features)} estimated metrics")
            return features

        except Exception as e:
            logger.error(f"Neutron estimates failed: {e}")
            return self._get_fallback_metrics()

    def _get_fallback_metrics(self):
        #Metriche di fallback
        logger.warning("Using fallback simulated metrics")

        return [{
            'resource_id': 'fallback-1',
            'resource_type': 'simulated',
            'resource_name': 'simulated-port',
            'features': [100.0, 80.0, 200, 180, 0.001, 5, 0.3, 1.0],
            'raw_metrics': {'simulated': True},
            'source': 'simulated'
        }]

    def get_generator_stats(self):
        #Restituisce statistiche del generatore
        return self.traffic_generator.get_stats()

    def get_cycle_count(self):
        #Restituisce il conteggio dei cicli
        return self.cycle_count
