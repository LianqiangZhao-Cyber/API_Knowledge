from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import os

app = Flask(__name__)

# 配置Flask和SQLite数据库
zID = '5396332'  # 替换为你的zID
db_filename = f'z{zID}.db'
current_dir = os.getcwd()
db_path = os.path.join(current_dir, db_filename)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 定义数据库模型
class Stop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stop_id = db.Column(db.Integer, unique=True, nullable=False)
    last_updated = db.Column(db.String, nullable=False)
    self_link = db.Column(db.String, nullable=False)

    def to_dict(self):
        return {
            "stop_id": self.stop_id,
            "last_updated": self.last_updated,
            "_links": {
                "self": {
                    "href": self.self_link
                }
            }
        }


# 创建数据库
if not os.path.exists(db_path):
    with app.app_context():
        db.create_all()
        
@app.route('/sdd')
def hello():
    return 'Welcome to My Watchlist!'


@app.route('/stops', methods=['GET','PUT'])
def add_stops():
    
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Missing query parameter"}), 400

    try:
        response = requests.get(f'https://v6.db.transport.rest/locations', params={
            'query': query,
            'poi': 'false',
            'addresses': 'false'
        })
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch data from Deutsche Bahn API"}), 503

        data = response.json()
        data = sorted(data, key=lambda x: x['id'])
        result = []
        for stop in data[:5]:
            stop_id = stop['id']
            now = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
            self_link = f"http://localhost:5000/stops/{stop_id}"

            existing_stop = Stop.query.filter_by(stop_id=stop_id).first()
            if existing_stop:
                existing_stop.last_updated = now
                existing_stop.self_link = self_link
                db.session.commit()
                result.append(existing_stop.to_dict())
            else:
                new_stop = Stop(stop_id=stop_id, last_updated=now, self_link=self_link)
                db.session.add(new_stop)
                db.session.commit()
                result.append(new_stop.to_dict())

        formatted_result = []
                
        for item in result:
            formatted_result.append({
                "stop_id": item["stop_id"],
                "last_updated": item["last_updated"],
                "_links": {
                    "self": {
                        "href": item["_links"]["self"]["href"]
                    }
                }
            })
        return jsonify(formatted_result), 201 if len(formatted_result) > 0 else 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
