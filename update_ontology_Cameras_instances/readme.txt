
调整一下 脚本 update_ontology_Cameras_instances/update_camera_data.py
1、更换数据库配置
SOURCE_DB_HOST = "10.143.36.7"
SOURCE_DB_PORT = "31647"
SOURCE_DB_NAME = "edi_data"
SOURCE_DB_USER = "readonly"
SOURCE_DB_PASSWORD = "88UM6Joj7BhBPKjN0E1B"


2、把脚本里的表 algorithm_param_post_safeguard algorithm_param_post_safety_scenarios 换为 v_algorithm_param_post_roi
 区别就是 type = 'post_safeguard' or 'post_safety_scenarios'


数据库配置：
172.16.11.20
54332
postgres
postgres

3、我给你一个 StandId，根据这个 StandId 查询 object_instances 表中 object_type_api_name 为 "Stand" 的记录，并获取对应 StandId 的 properties 字段中的 cameraID 列表。
数据示例：
执行SQL语句，查询object_instances表中object_type_api_name为"Stand"的记录, 拿到 properties 字段 ：{"ID": "213", "standID": "213", "cameraID": ["551937628299", "551937628300"], "category": "213", "aeroplaneInPosition": "false"}

然后根据 properties字段中的cameraID，遍历 cameraID ,
执行 SELECT * FROM object_instances
  WHERE "object_type_api_name" = 'Camera'
  AND "state" = 'ACTIVE'
  AND "properties"::text LIKE '%55127332242%'
	ORDER BY created_at desc ;
	，拿到properties字段数据。

4、获取 Camera实例的记录  示例数据：properties字段数据
{"name": "4034(新)", "index": [], "point": [], "areaCode": "234", "cameraID": "551932025727", "geopoint": [], "isActive": true, "postSafeguard": [], "safetyScenarios": []}
写一个方法 update_camera_instance(camera_id, new_properties) 来更新 Camera实例的properties字段数据 新的数据需要从表 v_algorithm_param_post_roi 里查询获取。
然后根据实例 id 更新这个实例的properties字段的数据。

object_instances 表结构：
CREATE TABLE "public"."object_instances" (
  "id" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "object_type_id" uuid NOT NULL,
  "object_type_api_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "properties" jsonb NOT NULL,
  "version" int4 NOT NULL DEFAULT 1,
  "state" varchar(50) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'ACTIVE'::character varying,
  "last_updated" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "last_synced_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "source_id" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "metadata" jsonb NOT NULL DEFAULT '{}'::jsonb,
  "property_metadata" jsonb NOT NULL DEFAULT '{}'::jsonb,
  "created_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamptz(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT "object_instances_pkey" PRIMARY KEY ("id")
);

