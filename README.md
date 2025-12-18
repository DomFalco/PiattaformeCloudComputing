# AI Anomaly Detection Plugin for OpenStack ☁️🛡️

> Progetto del corso di Piattaforme di Cloud Computing.

Questo repository ospita un **plug-in per OpenStack** progettato per monitorare e analizzare il traffico di rete in tempo reale su infrastrutture **Open vSwitch (OVS)**. Utilizzando tecniche di Machine Learning, il sistema è in grado di identificare pattern di traffico anomali (sia in entrata che in uscita).

---

## 📂 Struttura del Progetto

Il sistema è modulare e si compone dei seguenti componenti principali:

### 1. 📡 COLLECTOR (`collector_ovs.py`)
È il modulo responsabile dell'acquisizione dati.
* Si interfaccia con **Open vSwitch** e **Neutron** per estrarre le metriche di rete.
* Calcola i delta di traffico (velocità reale) invece dei semplici contatori cumulativi.
* Include una modalità di test per generare metriche simulate.

### 2. 🧠 DETECTOR (`detector.py`)
Il cuore intelligente del sistema.
* Utilizza l'algoritmo **Isolation Forest** (Unsupervised Learning).
* **Apprendimento Continuo:** Al primo avvio si addestra su un dataset sintetico (1000 campioni). Successivamente, il modello viene ri-addestrato periodicamente integrando i nuovi campioni reali raccolti, migliorando la precisione nel tempo.

### 3. 📊 REPORTER (`reporter.py`)
Gestisce l'output e la visualizzazione dei risultati.
* Distingue chiaramente le anomalie rilevate con tag specifici:
    * `[REAL]`: Anomalia rilevata su traffico effettivo.
    * `[SIMULATED]`: Anomalia rilevata durante i test di simulazione interna.

### 4. 🚀 MAIN (`main.py`)
L'entry point dell'applicazione.
* Orchestra l'esecuzione ciclica di Collector, Detector e Reporter.
* Gestisce il loop di monitoraggio e la gestione degli errori.

### 5. ⚡ TRAFFIC GENERATOR (`traffic_generator.py`)
Script di supporto per lo stress-test.
* Genera un flood di pacchetti UDP verso una destinazione per simulare un attacco o un picco anomalo di traffico.
* Essenziale per verificare che il Detector scatti correttamente in scenari reali.

---

## 🛠️ Guida al Testing: Simulazione di un'Anomalia Reale

Per verificare il funzionamento del plugin in uno scenario realistico, utilizzeremo un namespace Linux isolato ("testbox") per inviare traffico continuo verso OVS.

### Fase 1: Setup dell'Ambiente di Test
Esegui questi comandi sequenzialmente per creare una porta virtuale e collegarla a OVS:

```bash
# 1. Crea il namespace e i cavi virtuali
sudo ip netns add testbox
sudo ip link add veth_in type veth peer name veth_ovs

# 2. Sposta un capo del cavo nel namespace
sudo ip link set veth_in netns testbox

# 3. Collega l'altro capo a Open vSwitch (br-int)
sudo ovs-vsctl add-port br-int veth_ovs

# 4. Accendi le interfacce
sudo ip link set veth_ovs up
sudo ip netns exec testbox ip link set veth_in up

# 5. Assegna un IP e configura le rotte
sudo ip netns exec testbox ip addr add 192.168.99.1/24 dev veth_in
sudo ip netns exec testbox ip route add default dev veth_in

# 6. Configura ARP statico (per evitare overhead di rete)
sudo ip netns exec testbox ip neigh add 10.0.0.1 lladdr aa:bb:cc:dd:ee:ff dev veth_in

# 7. Avvio del generatore di traffico
sudo ip netns exec testbox python3 traffic_generator.py
```

### Fase 2: Pulizia (Cleanup) 🧹
Una volta terminato il test, è fondamentale rimuovere le risorse create per evitare falsi positivi o errori nei cicli successivi.

```bash
# 1. Rimuovi la porta da Open vSwitch
sudo ovs-vsctl del-port br-int veth_ovs

# 2. Cancella il namespace
# (Questa operazione distrugge automaticamente anche i cavi veth)
sudo ip netns del testbox

# 3. Verifica finale
echo "--- Verifica OVS (veth_ovs non deve esserci) ---"
sudo ovs-vsctl show | grep veth_ovs || echo "Tutto pulito!"
```
