
数据库配置：
postgres:16.11-alpine
172.16.11.18
54332
postgres
postgres

表结构：
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

现在需要你写个脚本
1、我给你一个 StandId，脚本会根据这个 StandId 查询 object_instances 表中 object_type_api_name 为 "Stand" 的记录，并获取对应 StandId 的 properties 字段中的 cameraID 列表。
1、首先执行SQL语句，查询object_instances表中object_type_api_name为"Stand"的记录, 拿到 properties 字段 ：{"ID": "213", "standID": "213", "cameraID": ["551937628299", "551937628300"], "category": "213", "aeroplaneInPosition": "false"}
然后根据 properties字段中的cameraID，遍历 cameraID ,
执行 SELECT * FROM object_instances
  WHERE "object_type_api_name" = 'Camera'
  AND "state" = 'ACTIVE'
  AND "properties"::text LIKE '%55127332242%'
	ORDER BY created_at desc ;
	，拿到properties字段数据。
2、保存查询到的properties字段数据到一个新的json文件中，命名为 ${cameraID}.json


