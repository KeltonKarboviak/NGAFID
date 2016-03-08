import math
from LatLon import LatLon
from Vector3d import Vector3d
import os

class FlightAnalyzer:
    parameters = {}
    airports = {}
    approaches = {}
    approachID = 0
    timestamp = ""
    folder = ""
    flightID = ""

    def __init__(self, time, folder, a):
        self.timestamp = time
        self.folder = folder
        self.airports = a

    def analyze(self, flightID, p):
        self.parameters = p
        self.flightID = flightID
        self.clearApproaches()
        start = self.findInitialTakeOff()
        self.analyzeApproaches(start)
        self.outputToCSV()
        self.resetApproachID()
        return self.approaches

    '''
    This function will find the initial takeoff and return the first time value after the initial takeoff
    @return the first time index after the initial takeoff
    '''
    def findInitialTakeOff(self):
        i = 0
        airplaneMSL = self.parameters[1]['data'][i]
        airplaneLat = self.parameters[10]['data'][i]
        airplaneLon = self.parameters[11]['data'][i]
        airport = self.detectAirport(airplaneLat, airplaneLon)
        hAGL = airplaneMSL - airport.alt
        while hAGL < 500 and i < len(self.parameters[0]['data']):
            airplaneMSL = self.parameters[1]['data'][i]
            hAGL = airplaneMSL - airport.alt
            i += 1
        return i


    '''
    This function analyzes the flight data.
    So far we have implemented a check for full stops.
    @param startingIndex the time index after the initial takeoff
    @author: Wyatt Hedrick, Kelton Karboviak
    '''
    def analyzeApproaches(self, startingIndex):
        i = startingIndex
        while i < len(self.parameters[0]['data']):
            airplaneMSL = self.parameters[1]['data'][i]
            airplaneLat =self.parameters[10]['data'][i]
            airplaneLon = self.parameters[11]['data'][i]

            airport = self.detectAirport(airplaneLat, airplaneLon)
            distance = self.haversine(airplaneLat, airplaneLon, airport.lat, airport.lon)
            hAGL = airplaneMSL - airport.alt

            if (distance < 1 and hAGL < 500):
                print "Airplane is approaching %s, %s" % (airport.city, airport.state)
                thisApproachID = self.getApproachID()
                self.approaches[thisApproachID] = {}
                self.approaches[thisApproachID]['unstable'] = []
                temp_list = []
                while hAGL > 150 and hAGL < 500:
                    i += 1
                    airplaneMSL = self.parameters[1]['data'][i]
                    hAGL = airplaneMSL - airport.alt
                # end while

                start = i

                airplaneLat = self.parameters[10]['data'][i]
                airplaneLon = self.parameters[11]['data'][i]
                airplaneHdg = self.parameters[4]['data'][i]

                runway = self.detectRunway(airplaneLat, airplaneLon, airplaneHdg, airport)
                unstableReasons = [ [], [], [], [] ]  # F1, F2, A, S
                while distance < 1 and hAGL <= 150 and hAGL >= 50:
                    airplaneHdg = self.parameters[4]['data'][i]
                    airplaneIAS = self.parameters[2]['data'][i]
                    airplaneVAS = self.parameters[3]['data'][i]

                    if runway is not None:
                        cond_F1 = 180 - abs(abs(runway.magHeading - airplaneHdg) - 180) <= 10
                        cond_F2 = abs(self.crossTrackToCenterLine(airplaneLat, airplaneLon, runway)) <= 50
                    else:
                        cond_F1 = cond_F2 = True
                    cond_A = airplaneIAS >= 55 and airplaneIAS <= 75
                    cond_S = airplaneVAS >= -1000
                    if not cond_F1 or not cond_F2 or not cond_A or not cond_S:
                        print "F1=%s, F2=%s, A=%s, S=%s" % (cond_F1, cond_F2, cond_A, cond_S)
                        if not cond_F1:
                            print "\tRunway Heading: %s" % runway.magHeading
                            print "\tAirplane Heading: %s" % airplaneHdg
                            unstableReasons[0].append(airplaneHdg)
                        if not cond_F2:
                            print "\tCrossTrackToCenterLine: %s" % self.crossTrackToCenterLine(airplaneLat, airplaneLon, runway)
                            unstableReasons[1].append( self.crossTrackToCenterLine(airplaneLat, airplaneLon, runway) )
                        if not cond_A:
                            print "\tIndicated Airspeed: %s knots" % (airplaneIAS)
                            unstableReasons[2].append(airplaneIAS)
                        if not cond_S:
                            print "\tVertical Airspeed: %s ft/min" % (airplaneVAS)
                            unstableReasons[3].append(airplaneVAS)
                        temp_list.append(i)
                    elif len(temp_list) > 0:
                        self.approaches[thisApproachID]['unstable'].append( (temp_list[0], temp_list[-1]) )
                        del temp_list[:]
                    i += 1

                    airplaneMSL = self.parameters[1]['data'][i]
                    airplaneLat = self.parameters[10]['data'][i]
                    airplaneLon = self.parameters[11]['data'][i]
                    distance = self.haversine(airplaneLat, airplaneLon, airport.lat, airport.lon)
                    hAGL = airplaneMSL - airport.alt
                # end while

                end = start if start == i else i - 1

                if len(temp_list) > 0:
                    self.approaches[thisApproachID]['unstable'].append( (temp_list[0], temp_list[-1]) )
                # end if

                self.approaches[thisApproachID]['F1'] = unstableReasons[0]
                self.approaches[thisApproachID]['F2'] = unstableReasons[1]
                self.approaches[thisApproachID]['A']  = unstableReasons[2]
                self.approaches[thisApproachID]['S']  = unstableReasons[3]

                i = self.analyzeLanding(end, airport, thisApproachID)
            # end if

            i += 15
        # end while

    '''
    This function will analyze the time after the final approach and before the plane reaches a height of 150 feet (or until the flight ends if it is the final landing).
    @param: start the time index when the approach ends and the landing begins.
    @param: airport the airport that the airplane is attempting to land at
    @author: Wyatt Hedrick
    '''
    def analyzeLanding(self, start, airport, thisApproachID):
        i = start
        airplaneMSL = self.parameters[1]['data'][i]
        hAGL = airplaneMSL - airport.alt
        fullStop = False
        elevations = []
        deltaElevation = 6

        fullStop = touchAndGo = False

        while hAGL < 500 and i < len(self.parameters[0]['data']) - 1:
            airplaneIAS = self.parameters[2]['data'][i]
            if (not fullStop):
                if airplaneIAS <= 35:
                    fullStop = True
                elif deltaElevation <= 5:
                    touchAndGo = True
            i += 1
            airplaneMSL = self.parameters[1]['data'][i]
            hAGL = airplaneMSL - airport.alt
            if len(elevations) < 5:
                elevations.append(hAGL)
            else:
                elevations.pop(0)
                elevations.append(hAGL)
                deltaElevation = sum(elevations)/len(elevations)
        end = i

        if fullStop:
            self.approaches[thisApproachID]['landing-type'] = 'stop-and-go'
            print "Full Stop!!!!"
        elif touchAndGo:
            self.approaches[thisApproachID]['landing-type'] = 'touch-and-go'
            print "Touch and Go!!!!"
        else:
            self.approaches[thisApproachID]['landing-type'] = 'go-around'
            print "Go Around?!?!?!"

        self.approaches[thisApproachID]['airport-code'] = airport.code
        self.approaches[thisApproachID]['landing-start'] = start
        self.approaches[thisApproachID]['landing-end'] = end
        print ""
        return end


    '''
    This function calculates the distance the airplane is from the center line in feet based on the passed in coordinates of the airplane and the runway the plane is attempting to land at.

    GIS Mapping Tool for verification: http://gistools.igismap.com/bearing

    @param: airplaneLat the latitude of the airplane
    @param: airplaneLon the longitude of the airplane
    @param: runway the runway object representing the closest runway to the airplane
    @returns: the distance in feet between the airplane and the center line of the runway
    @author: Wyatt Hedrick, Kelton Karboviak
    '''
    def crossTrackToCenterLine(self, airplaneLat, airplaneLon, runway):
        EARTH_RADIUS_FEET = 20900000  # Radius of the earth in feet
        airplanePoint = LatLon(airplaneLat, airplaneLon)
        runwayCenter = LatLon(runway.centerLat, runway.centerLon)
        hdg = runway.trueHeading

        return airplanePoint.crossTrackDistanceTo(runwayCenter, hdg, EARTH_RADIUS_FEET)


    '''
    This function calculates the distance (in miles) between 2 coordinates.
    Obtained formula from: http://www.movable-type.co.uk/scripts/latlong.html
    @param: lat1 the latitude of the first point
    @param: lon1 the longitude of the first point
    @param: lat2 the latitude of the second point
    @param: lon2 the longitude of the second point
    @param: radius (Mean) radius of earth (defaults to radius in miles)
    @return: the distance between the 2 points, in same units as radius
    @author: Wyatt Hedrick, Kelton Karboviak
    '''
    def haversine(self, lat1, lon1, lat2, lon2, radius=None):
        radius = 3959 if radius is None else radius

        rLat1 = math.radians(lat1)
        rLat2 = math.radians(lat2)
        deltaLat = math.radians( lat2 - lat1 )
        deltaLon = math.radians( lon2 - lon1 )

        a = math.sin(deltaLat/2) ** 2 +                   \
            math.cos(rLat1) * math.cos(rLat2) *           \
            math.sin(deltaLon/2) ** 2
        c = 2 * math.atan2( math.sqrt(a), math.sqrt(1-a) )
        d = radius * c
        return d # distance between the two points in miles

    '''
    This function detects the airport that is closest to the passed in coordinates.
    It performs this by scanning the airportData dictionary and calculating which
        airport as the lowest total difference between lat/lon.
    @param: lat the latitude of the plane
    @param: lon the longitude of the plane
    @author: Wyatt Hedrick
        # TODO Check altitude between plane and airport - Wyatt
        # TODO Have function return True/False on whether the plane is going to approach the airport
            (i.e. going in for a landing) - Kelton
    '''
    def detectAirport(self, lat, lon):
        closestAirport = -1
        closestDifference = 0
        for key in self.airports:
            airportLat = self.airports[key].lat
            airportLon = self.airports[key].lon
            dLat = abs(lat - airportLat) # getting difference in lat and lon
            dLon = abs(lon - airportLon)
            totalDifference = dLat + dLon # adding the differences so we can compare and see which airport is the closest
            if closestAirport == -1 or totalDifference < closestDifference: # if it is the first time or we found a closer airport
                closestDifference = totalDifference
                closestAirport = key

        return self.airports[closestAirport]


    '''
    This function will detect the runway that the airplane is going to attempt to land at.
    @param: airplaneLat the latitude of the airplane
    @param: airplaneLon the longitude of the airplane
    @param: airplaneHdg the heading of the heading
    @param: airport the airport object that represents the closest airport to the airplane
    @returns: the runway object representing the runway the airplane is attempting to land on
    @author: Wyatt Hedrick, Kelton Karboviak
    '''
    def detectRunway(self, airplaneLat, airplaneLon, airplaneHdg, airport):
        ourRunway = None
        closestDifference = -1
        for runway in airport.runways:
            if 180 - abs(abs(runway.magHeading - airplaneHdg) - 180) <= 20:
                dLat = abs(runway.centerLat - airplaneLat) # getting difference in lat and lon
                dLon = abs(runway.centerLon - airplaneLon)
                totalDifference = dLat + dLon
                if ourRunway is None or totalDifference < closestDifference:
                    ourRunway = runway
                    closestDifference = totalDifference

        return ourRunway

    '''
    Outputs the approach analysis information to a .csv file. The file will be saved to
        ./results/results_flightID.csv, and appended to ./results/query_timestamp.csv
    @param flightID string of the current flight ID to write to a CSV file
    @param timestamp string of the timestamp when the program started running.
        This will be used as the filename to store the results of all flights for this program run
    @param folder string of the folder in which to store the result CSV file
    @author: Kelton Karboviak
    '''
    def outputToCSV(self):
        with open('%s/query_%s.csv' % (self.folder, self.timestamp), 'a') as globalOutput:
            with open('%s/results_%s.csv' % (self.folder, self.flightID), 'w') as output:
                header = 'Flight_ID,Approach_ID,Airport_ID,Landing_Start,Landing_End,Landing_Type,Unstable?,F1_Heading,F2_CT,A_IAS,S_VAS\n'
                if os.stat(globalOutput.name).st_size == 0:
                    globalOutput.write(header)
                output.write(header)
                for ID, approach in self.approaches.items():
                    lineToWrite = '%s,%d,%s,%d,%d,%s,%s,%s,%s,%s,%s\n' % \
                                  (self.flightID,
                                   ID,
                                   approach['airport-code'],
                                   approach['landing-start'],
                                   approach['landing-end'],
                                   approach['landing-type'],
                                   'Y' if len(approach['unstable']) > 0 else 'N',
                                   "-" if len(approach['F1']) == 0 else sum(approach['F1'])/len(approach['F1']),
                                   "-" if len(approach['F2']) == 0 else sum(approach['F2'])/len(approach['F2']),
                                   "-" if len(approach['A'])  == 0 else sum(approach['A'])/len(approach['A']),
                                   "-" if len(approach['S'])  == 0 else sum(approach['S'])/len(approach['S']))
                    globalOutput.write(lineToWrite)
                    output.write(lineToWrite)
                # end for
            # end with
        # end with

    '''
    Function clears the contents of the approaches dictionary
    @author: Kelton Karboviak
    '''
    def clearApproaches(self):
        for key in self.approaches.keys():
            del self.approaches[key]

    '''
    This function will reset the approachID to 0 on the start of a new flight.
    @author Wyatt Hedrick, Kelton Karboviak
    '''
    def resetApproachID(self):
        self.approachID = 0

    '''
    This function will return a unique approachID for each approach in the flight.
    @returns aID the unique approachID associated with the approach.
    @author Wyatt Hedrick, Kelton Karboviak
    '''
    def getApproachID(self):
        aID = self.approachID
        self.approachID += 1
        return aID
