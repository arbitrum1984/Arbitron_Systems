"""Service for fetching corporate and billionaire private jet data from OpenSky Network.

This model provides context to the AI about the real-time physical locations
of key executives and economic figures, which can be useful for predicting
mergers, deals, or market sentiment.
"""

import httpx
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class OpenSkyService:
    def __init__(self):
        self._cached_summary = "OpenSky Network flight data currently initializing..."
        self._last_update = None
        self._raw_flights = []
        self._http_client = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": "ArbitronTerminalBot/1.0"}
        )
        
        # A curated list of business jets + military/presidential aircraft (ICAO24 hex codes)
        self.target_jets = {
            # --- Corporate / Billionaire Jets ---
            "a835af": "Elon Musk (N628TS)",
            "a64bb3": "SpaceX Corporate (N502SX)",
            "a05952": "Jeff Bezos (N11AF)",
            "a001fb": "Tim Cook / Apple (N1CV)",
            "a0e28f": "Mark Zuckerberg (N1955Q)",
            "a4d5e7": "Bill Gates (N887WM)",
            "a1dbe2": "Bill Gates 2 (N194WM)",
            "a21226": "Larry Ellison (N21ZE)",
            "a16104": "Google Corporate (N272BG)",
            "a01a3c": "Taylor Swift (N898TS)", 
            "38102f": "Bernard Arnault (F-GVMA)",
            "a3e49e": "Ken Griffin / Citadel (N68KP)",
            "a45c8c": "Steve Schwarzman / Blackstone (N500KS)",
            "a4d9c4": "Jamie Dimon / JPMorgan (N200JP)",
            "a295db": "Mark Cuban (N830MA)",
            # --- Presidential Aircraft (Air Force One) ---
            "ae0001": "🇺🇸 Air Force One VC-25A (82-8000)",
            "ae0002": "🇺🇸 Air Force One VC-25A (92-9000)",
            # --- E-4B Nightwatch (Doomsday / NAOC) ---
            "ae041a": "☢️ E-4B Nightwatch #1 (73-1676)",
            "ae041b": "☢️ E-4B Nightwatch #2 (73-1677)",
            "ae041c": "☢️ E-4B Nightwatch #3 (74-0787)",
            "ae041d": "☢️ E-4B Nightwatch #4 (75-0125)",
            # --- E-6B Mercury (Looking Glass / TACAMO) ---
            "ae1496": "⚡ E-6B Mercury TACAMO #1",
            "ae1497": "⚡ E-6B Mercury TACAMO #2",
            # --- C-32A (Vice President / Senior Leaders) ---
            "ae4aa5": "🇺🇸 C-32A VP Aircraft (98-0001)",
            "ae4aa6": "🇺🇸 C-32A VP Aircraft (98-0002)",
        }
        
    async def update_flights_background(self):
        """Update flight data in the background using the OpenSky API."""
        logger.info("[OpenSky Service] Fetching new aircraft data...")
        
        icao24_str = "&icao24=".join(self.target_jets.keys())
        url = f"https://opensky-network.org/api/states/all?icao24={icao24_str}"
        
        try:
            response = await self._http_client.get(url)
            
            if response.status_code == 429:
                logger.warning("[OpenSky Service] Rate limited. Will retry later.")
                if "currently initializing" in self._cached_summary:
                    self._cached_summary = "OpenSky API rate limit reached. Awaiting cooldown."
                return
            
            response.raise_for_status()
            data = response.json()
            
            states = data.get("states")
            
            # Active flights for the UI
            self._raw_flights = []
            
            # Create a textual summary for the AI
            summary_lines = []
            summary_lines.append("--- CORPORATE JET TRACKER (OPENSKY NETWORK) ---")
            
            if not states:
                summary_lines.append("No targeted corporate jets are currently airborne emitting ADS-B pings.")
            else:
                for state in states:
                    icao24 = state[0]
                    callsign = state[1].strip() if state[1] else "UNKNOWN"
                    lon = state[5]
                    lat = state[6]
                    altitude_meters = state[7]
                    on_ground = state[8]
                    velocity_mps = state[9]
                    
                    owner_name = self.target_jets.get(icao24, "Unknown Jet")
                    
                    plane_details = {
                        "owner": owner_name,
                        "icao24": icao24,
                        "callsign": callsign,
                        "on_ground": on_ground,
                    }
                    
                    if on_ground or altitude_meters is None:
                        status_text = "ON GROUND/PARKED"
                        plane_details["altitude"] = 0
                        plane_details["speed"] = 0
                        plane_details["location"] = f"Lat: {lat}, Lon: {lon}" if lat and lon else "Unknown Loc"
                    else:
                        altitude_ft = int(altitude_meters * 3.28084)
                        speed_kts = int(velocity_mps * 1.94384) if velocity_mps else 0
                        status_text = f"AIRBORNE (Alt: {altitude_ft} ft, Spd: {speed_kts} kts, Lat: {lat:.2f}, Lon: {lon:.2f})"
                        
                        plane_details["altitude"] = altitude_ft
                        plane_details["speed"] = speed_kts
                        plane_details["location"] = f"{lat:.2f}, {lon:.2f}"
                        
                    self._raw_flights.append(plane_details)
                    summary_lines.append(f"{owner_name} ({icao24}): {status_text}")
            
            # Also list the ones that didn't ping recently
            pinged_hexes = [s[0] for s in states] if states else []
            for hex_code, owner in self.target_jets.items():
                if hex_code not in pinged_hexes:
                    summary_lines.append(f"{owner} ({hex_code}): NO RECENT PING (Assumed Off/Landed)")
                    self._raw_flights.append({
                        "owner": owner,
                        "icao24": hex_code,
                        "callsign": "N/A",
                        "on_ground": True,
                        "altitude": 0,
                        "speed": 0,
                        "location": "No recent ping"
                    })
            
            self._cached_summary = "\n".join(summary_lines)
            self._last_update = datetime.now()
            logger.info(f"[OpenSky Service] Updated {len(states) if states else 0} active flights.")
            
        except Exception as e:
            logger.error(f"[OpenSky Service] Failed to fetch data: {str(e)}")

    def get_summary(self) -> str:
        """Get the latest textual summary for the AI prompt."""
        return self._cached_summary
        
    def get_raw_flights(self):
        """Get the raw serialized JSON payload of flights for the UI."""
        return {
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "flights": self._raw_flights
        }

flight_tracker = OpenSkyService()
