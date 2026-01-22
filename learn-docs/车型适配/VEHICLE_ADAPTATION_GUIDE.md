# openpilot Vehicle Adaptation Guide

## Overview

This guide explains the openpilot software architecture for vehicle support and provides step-by-step instructions for adding new vehicle model adaptations.

---

## 1. Software Architecture Overview

### 1.1 Core Directory Structure

```
openpilot/
├── opendbc_repo/opendbc/car/          # Vehicle-specific implementations
│   ├── volkswagen/                     # Brand-specific folder
│   │   ├── values.py                   # Vehicle definitions & parameters
│   │   ├── fingerprints.py             # CAN fingerprints for identification
│   │   ├── interface.py                # Main interface implementation
│   │   ├── carstate.py                 # Vehicle state parsing
│   │   ├── carcontroller.py            # Control commands
│   │   ├── radar_interface.py          # Radar data processing (if applicable)
│   │   └── *can.py                     # CAN message builders (mqbcan.py, mlbcan.py, etc.)
│   ├── toyota/                         # Other brand examples
│   ├── honda/
│   └── ...
├── opendbc_repo/opendbc/dbc/          # CAN database files
│   ├── vw_mqb.dbc                      # VW MQB platform DBC
│   ├── vw_mlb.dbc                      # VW MLB platform DBC
│   ├── vw_pq.dbc                       # VW PQ platform DBC
│   └── ...
├── selfdrive/car/                      # High-level car interface
│   ├── car_specific.py                 # Car-specific logic
│   ├── card.py                         # Car daemon
│   └── ...
└── panda/                              # Hardware interface (CAN communication)
    └── board/safety/                   # Safety models
```

### 1.2 Key Components

#### A. **values.py** - Vehicle Definitions
- Defines all supported vehicle models (CAR enum)
- Contains vehicle specifications (mass, wheelbase, steer ratio)
- Platform configurations (DBC files, chassis codes, WMI codes)
- Safety flags and feature flags
- Controller parameters (steering limits, acceleration limits)

#### B. **fingerprints.py** - Vehicle Identification
- CAN message fingerprints for each vehicle model
- ECU firmware versions (engine, transmission, EPS, radar, etc.)
- Used for automatic vehicle detection

#### C. **interface.py** - Main Interface
- Implements CarInterfaceBase
- Configures vehicle parameters
- Sets up safety configurations
- Defines lateral and longitudinal tuning

#### D. **carstate.py** - State Parsing
- Parses CAN messages to extract vehicle state
- Reads steering angle, speed, gear position, buttons, etc.
- Monitors driver engagement and safety conditions

#### E. **carcontroller.py** - Control Commands
- Generates CAN messages for vehicle control
- Implements steering (HCA), acceleration (ACC), and braking commands
- Handles safety interlocks and timeouts

#### F. **DBC Files** - CAN Message Definitions
- Define CAN message structures
- Signal names, scaling, offsets
- Message IDs and frequencies

---

## 2. Vehicle Identification System

### 2.1 Fingerprinting Process

openpilot identifies vehicles using two methods:

1. **CAN Fingerprinting**: Matches CAN message IDs present on the bus
2. **Firmware Fingerprinting**: Matches ECU firmware versions via UDS queries
3. **VIN Matching**: Uses VIN WMI (World Manufacturer Identifier) and chassis code

### 2.2 Fingerprint Structure

```python
FW_VERSIONS = {
  CAR.VOLKSWAGEN_GOLF_MK7: {
    (Ecu.engine, 0x7e0, None): [
      b'\xf1\x8704E906024K \xf1\x896811',
      # Multiple firmware versions supported
    ],
    (Ecu.transmission, 0x7e1, None): [...],
    (Ecu.srs, 0x715, None): [...],
    (Ecu.eps, 0x712, None): [...],
    (Ecu.fwdRadar, 0x757, None): [...],
  },
}
```

---

## 3. Adding a New Vehicle Model

### Step 1: Collect Vehicle Fingerprint

#### 1.1 Get CAN Fingerprint

Use the fingerprint collection script:

```bash
cd /home/wio/openpilot
python selfdrive/debug/get_fingerprint.py
```

**Requirements:**
- Connect Panda device to vehicle OBD-II port
- Run `selfdrive/pandad/pandad` in another terminal
- Keep car in stock mode (no openpilot control)
- Run for at least 30 seconds to capture all messages

**Output Example:**
```
number of messages 45:
fingerprint 128: 8, 170: 8, 173: 8, 288: 4, 289: 8, ...
```

Save this fingerprint data.

#### 1.2 Get Firmware Versions

Use the firmware query script:

```bash
python selfdrive/debug/fingerprint_from_route.py
```

Or query directly from vehicle:
```bash
python panda/examples/query_fw_versions.py
```

This will return ECU firmware versions for:
- Engine (0x7e0)
- Transmission (0x7e1)
- ABS/ESP (0x715)
- EPS (0x712)
- Radar (0x757)

#### 1.3 Get VIN Information

```bash
python panda/examples/query_vin_and_stats.py
```

Extract:
- WMI (first 3 characters): e.g., "WVW" for VW Europe
- Chassis code (characters 7-8): e.g., "BU" for Jetta MK7

---

### Step 2: Determine Platform

Identify which platform your vehicle belongs to:

**Volkswagen Platforms:**
- **PQ Platform** (older): Jetta MK6, Passat NMS, Sharan MK2, Caddy MK3
- **MQB Platform** (current): Golf MK7, Tiguan MK2, Passat MK8, Arteon
- **MLB Platform** (Audi/Porsche): Macan, Q7, A4/A5/A6/A7

Check existing similar models in `values.py` to determine platform.

---

### Step 3: Add Vehicle Definition to values.py

#### 3.1 Add to CAR Enum

```python
class CAR(Platforms):
  config: VolkswagenMQBPlatformConfig | VolkswagenPQPlatformConfig
  
  # Add your new vehicle
  VOLKSWAGEN_SAGITAR_2024 = VolkswagenMQBPlatformConfig(
    [
      VWCarDocs("Volkswagen Sagitar 2024"),
    ],
    VolkswagenCarSpecs(
      mass=1450,              # Vehicle mass in kg
      wheelbase=2.68,         # Wheelbase in meters
      steerRatio=15.6,        # Steering ratio
    ),
    chassis_codes={"BU"},     # From VIN characters 7-8
    wmis={WMI.SAIC_VOLKSWAGEN},  # From VIN characters 1-3
  )
```

#### 3.2 Configure Platform-Specific Parameters

If using a new platform configuration:

```python
@dataclass
class VolkswagenMQBPlatformConfig(PlatformConfig):
  dbc_dict: DbcDict = field(default_factory=lambda: {Bus.pt: 'vw_mqb'})
  chassis_codes: set[str] = field(default_factory=set)
  wmis: set[WMI] = field(default_factory=set)
```

---

### Step 4: Add Fingerprints to fingerprints.py

Add your collected fingerprints:

```python
FW_VERSIONS = {
  # ... existing vehicles ...
  
  CAR.VOLKSWAGEN_SAGITAR_2024: {
    (Ecu.engine, 0x7e0, None): [
      b'\xf1\x8704E906024XX\xf1\x89XXXX',  # Your firmware version
    ],
    (Ecu.transmission, 0x7e1, None): [
      b'\xf1\x8709G927158XX\xf1\x89XXXX',
    ],
    (Ecu.srs, 0x715, None): [
      b'\xf1\x875Q0959655XX\xf1\x89XXXX\xf1\x82...',
    ],
    (Ecu.eps, 0x712, None): [
      b'\xf1\x875Q0909144XX\xf1\x89XXXX\xf1\x82...',
    ],
    (Ecu.fwdRadar, 0x757, None): [
      b'\xf1\x872Q0907572XX\xf1\x89XXXX',
    ],
  },
}
```

---

### Step 5: Configure DBC File

#### 5.1 Check if Existing DBC Works

Most VW vehicles share DBC files by platform:
- MQB → `vw_mqb.dbc`
- MLB → `vw_mlb.dbc`
- PQ → `vw_pq.dbc`

#### 5.2 Create Custom DBC (if needed)

If your vehicle has unique CAN messages:

1. Use Cabana tool to analyze CAN traffic:
```bash
tools/cabana/cabana
```

2. Export DBC file to `opendbc_repo/opendbc/dbc/`

3. Update platform config in `values.py`:
```python
dbc_dict: DbcDict = field(default_factory=lambda: {Bus.pt: 'vw_sagitar_2024'})
```

---

### Step 6: Implement/Verify carstate.py

Check if existing carstate.py works for your vehicle. Key signals to verify:

```python
def update(self, can_parsers):
  # Steering angle
  self.steering_angle = can_parsers.pt.vl["LWI_01"]["LWI_Lenkradwinkel"]
  
  # Vehicle speed
  self.v_ego = can_parsers.pt.vl["ESP_19"]["ESP_VSignal"] * CV.KPH_TO_MS
  
  # Gear position
  self.gear_shifter = self.parse_gear_shifter(...)
  
  # Brake pedal
  self.brake_pressed = can_parsers.pt.vl["ESP_05"]["ESP_Fahrer_bremst"]
  
  # Gas pedal
  self.gas_pressed = can_parsers.pt.vl["Motor_20"]["MO_Fahrpedalrohwert_01"] > 0
  
  # Cruise control buttons
  self.button_events = self.create_button_events(...)
```

If signals are different, update the message/signal names.

---

### Step 7: Implement/Verify carcontroller.py

Verify control message generation:

```python
def update(self, CC, CS, now_nanos):
  # HCA steering control
  if self.frame % self.CCP.STEER_STEP == 0:
    can_sends.append(mqbcan.create_steering_control(...))
  
  # ACC control (if longitudinal control enabled)
  if self.frame % self.CCP.ACC_CONTROL_STEP == 0:
    can_sends.append(mqbcan.create_acc_control(...))
  
  # LDW/Lane Assist HUD
  if self.frame % self.CCP.LDW_STEP == 0:
    can_sends.append(mqbcan.create_lka_hud_control(...))
```

---

### Step 8: Configure interface.py

Update vehicle-specific parameters:

```python
@staticmethod
def _get_params(ret: structs.CarParams, candidate: CAR, ...):
  # ... existing code ...
  
  # Per-vehicle overrides
  if candidate == CAR.VOLKSWAGEN_SAGITAR_2024:
    # Adjust steering parameters if needed
    ret.lateralTuning.pid.kpV = [0.6]
    ret.lateralTuning.pid.kiV = [0.2]
    ret.lateralTuning.pid.kf = 0.00006
    
    # Adjust longitudinal parameters if needed
    ret.stopAccel = -0.55
    ret.vEgoStarting = 0.1
```

---

### Step 9: Test and Tune

#### 9.1 Initial Testing

1. **Bench test** with Panda connected to vehicle (engine off):
```bash
./selfdrive/manager/manager.py
```

2. Verify:
   - Vehicle is correctly identified
   - All signals are parsed correctly
   - No CAN errors

#### 9.2 On-Road Testing

1. **Test steering control**:
   - Verify smooth steering
   - Check for oscillations
   - Tune PID parameters if needed

2. **Test longitudinal control** (if enabled):
   - Verify acceleration/braking
   - Check for jerky behavior
   - Tune parameters if needed

3. **Safety testing**:
   - Verify driver override works
   - Check timeout behaviors
   - Test emergency situations

#### 9.3 Parameter Tuning

Adjust in `interface.py`:

```python
# Lateral tuning
ret.lateralTuning.pid.kpV = [0.6]  # Proportional gain
ret.lateralTuning.pid.kiV = [0.2]  # Integral gain
ret.lateralTuning.pid.kf = 0.00006  # Feedforward gain

# Steering limits
ret.steerActuatorDelay = 0.1  # Actuator delay in seconds
ret.steerLimitTimer = 0.4     # Time before limiting steering

# Longitudinal tuning
ret.stopAccel = -0.55         # Stopping acceleration
ret.vEgoStarting = 0.1        # Starting speed threshold
```

---

## 4. Special Considerations for Your VW Sagitar 2024

### 4.1 No ACC System

Since your vehicle doesn't have ACC:

```python
# In interface.py
ret.openpilotLongitudinalControl = False
ret.pcmCruise = False
ret.dashcamOnly = True  # Display-only mode
```

### 4.2 Lane Display Only

Focus on:
- Lane line detection visualization
- Path prediction display
- No steering control (unless you add hardware)

### 4.3 Camera Integration

If using external camera:
- Configure camera parameters in `system/camerad/`
- Set up video stream processing
- Calibrate camera mounting position

---

## 5. Testing Checklist

- [ ] Vehicle correctly identified by fingerprint
- [ ] All CAN signals parsed correctly
- [ ] Steering angle reads correctly
- [ ] Speed reads correctly
- [ ] Gear position reads correctly
- [ ] Brake/gas pedal states correct
- [ ] No CAN errors or warnings
- [ ] Lane lines detected and displayed
- [ ] Path prediction shown correctly
- [ ] System stable for extended driving

---

## 6. Common Issues and Solutions

### Issue 1: Vehicle Not Recognized
**Solution**: 
- Verify fingerprint is complete (run for 30+ seconds)
- Check VIN WMI and chassis code match
- Ensure firmware versions are added to fingerprints.py

### Issue 2: CAN Signals Not Parsing
**Solution**:
- Verify DBC file has correct message definitions
- Use Cabana to inspect actual CAN traffic
- Update signal names in carstate.py

### Issue 3: Steering Oscillations
**Solution**:
- Reduce kpV (proportional gain)
- Increase steerActuatorDelay
- Adjust STEER_DELTA_UP/DOWN rates

### Issue 4: CAN Bus Errors
**Solution**:
- Check Panda connection
- Verify correct CAN bus (pt, cam, ext)
- Check message frequencies match DBC

---

## 7. Reference Files for VW Sagitar 2024

Based on your vehicle being a 2024 VW Sagitar (likely MQB platform, similar to Jetta MK7):

**Reference vehicles to study:**
- `CAR.VOLKSWAGEN_JETTA_MK7` - Most similar
- `CAR.VOLKSWAGEN_GOLF_MK7` - Same platform
- `CAR.VOLKSWAGEN_TIGUAN_MK2` - Same platform

**Key files to modify:**
1. `/home/wio/openpilot/opendbc_repo/opendbc/car/volkswagen/values.py`
2. `/home/wio/openpilot/opendbc_repo/opendbc/car/volkswagen/fingerprints.py`
3. `/home/wio/openpilot/opendbc_repo/opendbc/car/volkswagen/interface.py`

**DBC file to use:**
- `/home/wio/openpilot/opendbc_repo/opendbc/dbc/vw_mqb.dbc`

---

## 8. Development Workflow

```bash
# 1. Collect fingerprint
cd /home/wio/openpilot
python selfdrive/debug/get_fingerprint.py > sagitar_fingerprint.txt

# 2. Query firmware
python panda/examples/query_fw_versions.py > sagitar_fw.txt

# 3. Edit values.py
vim opendbc_repo/opendbc/car/volkswagen/values.py

# 4. Edit fingerprints.py
vim opendbc_repo/opendbc/car/volkswagen/fingerprints.py

# 5. Test
./selfdrive/manager/manager.py

# 6. Analyze CAN traffic (if needed)
tools/cabana/cabana

# 7. Tune parameters
vim opendbc_repo/opendbc/car/volkswagen/interface.py
```

---

## 9. Additional Resources

- **Official openpilot docs**: https://docs.comma.ai
- **Car porting guide**: `/home/wio/openpilot/docs/car-porting/`
- **DBC documentation**: `/home/wio/openpilot/opendbc_repo/opendbc/dbc/README.md`
- **Cabana tool**: `/home/wio/openpilot/tools/cabana/README.md`
- **Community Discord**: https://discord.comma.ai

---

## 10. Summary

**Key Steps:**
1. ✅ Collect CAN fingerprint and firmware versions
2. ✅ Determine vehicle platform (MQB for Sagitar)
3. ✅ Add vehicle definition to values.py
4. ✅ Add fingerprints to fingerprints.py
5. ✅ Verify/update DBC file
6. ✅ Test and verify all signals
7. ✅ Tune parameters for smooth operation
8. ✅ Extensive on-road testing

**For your specific case (Sagitar 2024, no ACC):**
- Focus on lane display and prediction
- Use dashcam-only mode
- Reference Jetta MK7 implementation
- Use vw_mqb.dbc file
- No longitudinal control needed

Good luck with your vehicle adaptation! 🚗
