# Integrated Actuator --- Technical Specifications

  ---------------------------------------------------------------------------
  **Category**      **Specification**   **Category**      **Specification**
  ----------------- ------------------- ----------------- -------------------
  Application       Legged robot,       Peak torque       222 N·m
                    exoskeleton, AGV                      

  Driving method    FOC                 Peak current      18 A (DC)

  Operating         −20 to 50 °C        No-load speed     35 RPM
  temperature                                             

  Winding type      Delta               KV                41 RPM/V

  Insulation class  F                   KT                0.23 N·m/A

  Insulation        500 V, 5 mA / 2 s   KE                2.4 V/KRPM
  withstand voltage                                       

  Insulation        500 V, 10 MΩ        Phase-to-phase    0.56 Ω
  resistance                            resistance        

  Number of slots   36                  Phase-to-phase    0.6 mH
                                        inductance        

  Pole pairs        21                  Rotor inertia     1,170 g·cm²

  Reduction ratio   48:1                Motor constant    0.31 N·m/√W

  Back-drive torque 2.22 N·m            Mechanical time   2.28 ms
                                        constant          

  Backlash          12 arcmin           Maximum torque    159 N·m/kg
                                        density           

  Temperature       NTCMF51B103F3950    CAN connector     XT30PW (2+2)-M
  sensor                                                  

  Noise (measured   65 dB               UART connector    A1257WR-S-3P
  at 65 cm)                                               

  Basic dynamic     5,680 N             Power connector   XT30PW (2+2)-M
  load rating (C)                                         

  Basic static load 8,680 N             Inner-loop        Magnetic, 21-bit
  rating (C₀)                           encoder           

  Rated voltage     48 V                Outer-loop        Magnetic, 21-bit
                                        encoder           

  Rated torque      74 N·m              Number of         2
                                        encoders          

  Rated speed       28 RPM              Weight            1,396 g

  Rated current     6 A (DC)                              
  ---------------------------------------------------------------------------
