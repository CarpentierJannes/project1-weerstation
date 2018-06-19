from flask import Flask
from flask import render_template, request
from flaskext.mysql import MySQL
from datetime import datetime

app = Flask(__name__)
mysql = MySQL(app)

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = 'project1-web'
app.config['MYSQL_DATABASE_PASSWORD'] = 'webpassword'
app.config['MYSQL_DATABASE_DB'] = 'weerstation'
app.config['MYSQL_DATABASE_HOST'] = 'localhost'


def get_data(sql, params=None):
    conn = mysql.connect()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
    except Exception as e:
        print(e)
        return False

    result = cursor.fetchall()
    db_data = []
    for row in result:
        db_data.append(row)

    cursor.close()
    conn.close()

    return db_data


def set_data(sql, params=None):
    conn = mysql.connect()
    cursor = conn.cursor()
    print("Setting Data")
    try:
        cursor.execute(sql, params)
        conn.commit()
    except Exception as e:
        return False

    cursor.close()
    conn.close()

    return True


@app.route('/')
def index():
    # check if there is data for the last 24 hours
    if get_data("SELECT * FROM vw_data_day") == []:
        return render_template('base.html')

    # first graph (temp and hum of last 24h)
    graph1 = {
        'labels': [],
        'data': []
    }
    data = get_data("SELECT value,round_time_5min(entrydate) FROM vw_data_day WHERE sensorID = 1")
    dataset = {
        'label': 'temperatuur',
        'data': [],
        'color': 'rgba(255,0,0,1)'
    }
    for item in data:
        dataset['data'].append(item[0])
        graph1['labels'].append(datetime.time(item[1]))
    graph1['data'].append(dataset)
    data = get_data("SELECT value FROM vw_data_day WHERE sensorID = 2")
    dataset = {
        'label': 'luchtvochtigheid',
        'data': [],
        'color': 'rgba(0,0,255,1)'
    }
    for item in data:
        dataset['data'].append(item[0])
    graph1['data'].append(dataset)


    # second graph (rain)
    graph2 = {
        'labels': graph1['labels'],
        'data': [],
        'percentage': ''
    }
    data = get_data("SELECT value FROM vw_data_day WHERE sensorID = 4")
    dataset = {
        'label': 'neerslag',
        'data': [],
        'color': 'rgba(0,0,255,1)'
    }
    for item in data:
        dataset['data'].append(item[0])
    graph2['data'].append(dataset)
    percentage = get_data("SELECT (SELECT COUNT(*) FROM vw_data_day WHERE sensorID = 4 AND value != 0) / (SELECT COUNT(*) FROM vw_data_day WHERE sensorID = 4)")[0][0]
    graph2['percentage'] = int(percentage * 100)


    # current weather
    current_temp = get_data("SELECT value FROM data WHERE sensorID = (SELECT sensorID FROM sensor WHERE type='temperatuur') ORDER BY entrydate DESC LIMIT 1")[0][0]
    current_hum = get_data("SELECT value FROM data WHERE sensorID = (SELECT sensorID FROM sensor WHERE type='luchtvochtigheid') ORDER BY entrydate DESC LIMIT 1")[0][0]
    current_press = get_data("SELECT value FROM data WHERE sensorID = (SELECT sensorID FROM sensor WHERE type='luchtdruk') ORDER BY entrydate DESC LIMIT 1")[0][0]
    current_rain = get_data("SELECT value FROM data WHERE sensorID = (SELECT sensorID FROM sensor WHERE type='neerslag') ORDER BY entrydate DESC LIMIT 1")[0][0]
    currentweather = [
        '{0:.2f}'.format(current_temp) + '°C',
        '{0:.2f}'.format(current_hum) + '%',
        '{0:.2f}'.format(current_press) + 'mbar',
        '{0:.2f}'.format(current_rain) + 'mm'
    ]


    # statistics
    stats_data_day = get_data("SELECT MIN(value), MAX(value), AVG(value) FROM vw_data_day WHERE sensorID = 1")[0]
    stats_data_week = get_data("SELECT MIN(value), MAX(value), AVG(value) FROM vw_data_week WHERE sensorID = 1")[0]
    stats_data_month = get_data("SELECT MIN(value), MAX(value), AVG(value) FROM vw_data_month WHERE sensorID = 1")[0]
    stats_data_year = get_data("SELECT MIN(value), MAX(value), AVG(value) FROM vw_data_year WHERE sensorID = 1")[0]
    stats = [
        {
            'name': 'vandaag',
            'data': [
                ['min', '{0:.1f}'.format(stats_data_day[0])],
                ['max', '{0:.1f}'.format(stats_data_day[1])],
                ['avg', '{0:.1f}'.format(stats_data_day[2])]
            ]
        }, {
            'name': 'deze week',
            'data': [
                ['min', '{0:.1f}'.format(stats_data_week[0])],
                ['max', '{0:.1f}'.format(stats_data_week[1])],
                ['avg', '{0:.1f}'.format(stats_data_week[2])]
            ]
        }, {
            'name': 'deze maand',
            'data': [
                ['min', '{0:.1f}'.format(stats_data_month[0])],
                ['max', '{0:.1f}'.format(stats_data_month[1])],
                ['avg', '{0:.1f}'.format(stats_data_month[2])]
            ]
        }, {
            'name': 'dit jaar',
            'data': [
                ['min', '{0:.1f}'.format(stats_data_year[0])],
                ['max', '{0:.1f}'.format(stats_data_year[1])],
                ['avg', '{0:.1f}'.format(stats_data_year[2])]
            ]
        }
    ]
    return render_template('index.html', currentweather=currentweather, stats=stats, graph1=graph1, graph2=graph2)


@app.route('/chart', methods=['GET', 'POST'])
def chart():
    graph = {
        'labels': [],
        'data': [],
        'options': {
            'sensor': {
                'temperature': True, 'humidity': True, 'pressure': True, 'rainfall': True},
            'period': request.args.get('period', 'day'),
            'type': 'line'
        }
    }
    if graph["options"]["period"] not in ('hour', 'day', 'week', 'month', 'year'):
        graph["options"]["period"] = 'day'
    sensorIDs = get_data("SELECT sensorID, type, unit FROM sensor")
    colors = {'temperatuur': 'rgba(255,0,0,1)', 'luchtvochtigheid': 'rgba(0,128,255,1)', 'luchtdruk': 'rgba(0,255,0,1)', 'neerslag': 'rgba(0,0,255,1)'}
    times = set()
    for sensor in sensorIDs:
        data = get_data("SELECT value, round_time_5min(entrydate) FROM vw_data_{0} WHERE sensorID = %s ORDER BY entrydate ASC".format(graph["options"]["period"]), sensor[0])
        dataset = {
            'label': sensor[1],
            'data': [],
            'color': colors.get(sensor[1], 'rgba(255,0,0,1)'),
            'unit': sensor[2]
        }
        for item in data:
            dataset['data'].append(item[0])
            times.add(str(datetime.time(item[1])))
        graph['data'].append(dataset)
    times = list(times)
    times.sort()
    graph['labels'] = times
    return render_template('chart.html',graph=graph)


if __name__ == '__main__':
    app.run()
