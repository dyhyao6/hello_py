# Camera 实例 properties 数据结构说明

## 数据层级关系

```
object_instances 表
  ├── Stand 记录 (object_type_api_name='Stand')
  │     └── properties: {"standID": "213", "cameraID": ["551937628299", "551937628300"], ...}
  │           └── cameraID 列表关联到 Camera
  │
  └── Camera 记录 (object_type_api_name='Camera')，每个 Camera 独立存储
        └── properties (本文件描述的内容)
```

- **Stand** 和 **Camera** 是 `object_instances` 表中两条独立的记录
- **关系**：Stand 的 `properties.cameraID` 列表关联到多个 Camera 实例
- Stand 的 `properties` 示例：`{"standID": "213", "cameraID": ["551937628299", "551937628300"], "aeroplaneInPosition": "false"}`
- Camera 的 `properties` 示例：`{"name": "A0079-028机位左侧", "cameraID": "55108135936", "postSafeguard": [...], ...}`（本文档描述的内容）

---

## Stand properties 字段说明

Stand 记录中 properties 字段结构：

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `ID` | string | Stand ID | `"213"` |
| `standID` | string | 机位编号 | `"213"` |
| `cameraID` | array | 关联的摄像头ID列表 | `["551937628299", "551937628300"]` |
| `category` | string | 类别 | `"213"` |
| `aeroplaneInPosition` | string | 航班是否在位 | `"false"` |

**注意**：Camera 的 properties 不是嵌套在 Stand 里的，而是通过 `cameraID` 关联。

---

## 顶层字段

| 字段名 | 类型 | 说明                        | 示例 |
|--------|------|---------------------------|------|
| `name` | string | 摄像头名称                     | `"A0079-028机位左侧"` |
| `cameraID` | string | 摄像头唯一标识                   | `"55108135936"` |
| `areaCode` | string | 机位编号                      | `"028"` |
| `isActive` | boolean | 是否激活                      | `true` |
| `index` | array | 网格索引坐标数组，每项为 `[row, col]` | `[[-20, 0], [-20, 1], ...]` 长度: 2173 |
| `point` | array | 网格像素坐标数组，每项为 `[x, y]`     | `[[1847, 898], ...]` 长度: 2173 |
| `geopoint` | array | 经纬度坐标数组，每项为 `[lon, lat]`  | `[[121.7997..., 31.1467...], ...]` 长度: 41 |
| `postSafeguard` | array | 航班保障场景                    | 见下方详述 |
| `safetyScenarios` | array | 安全区飞行场景                   | 见下方详述 |

---

## index 和 point 的关系

- `index` 和 `point` 长度相同（均为 2173），一一对应
- `index[i]` 是网格逻辑坐标 `[row, col]`
- `point[i]` 是对应的像素坐标 `[x, y]`
- 通过这两个数组可以将网格逻辑坐标映射到实际像素位置

---

## postSafeguard / safetyScenarios 子项结构

每个子项结构相同，字段如下：

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `roi` | array | 区域多边形顶点坐标数组，每项为 `[x, y]` | `[[-5, 2], [-5, 3], ...]` |
| `name` | string | 区域名称 | `"tractor_roi"`, `"engine_roi"` |
| `type` | string | 类型标识 | `"post_safeguard"`, `"post_safety_scenarios"` |
| `area_title` | string | 区域显示名称 | `"tractor_roi"` |
| `aircraft_model` | string | 机型 | `"A321"` |
| `roi_of_detection` | array | 检测区域坐标数组 | `[]` |

---

## 示例：postSafeguard 子项

```json
{
  "roi": [
    [-5, 2],
    [-5, 3],
    [-5, 4]
  ],
  "name": "tractor_roi",
  "type": "post_safeguard",
  "area_title": "tractor_roi",
  "aircraft_model": "A321",
  "roi_of_detection": []
}
```

---

## 数据用途

- `index` / `point`: 用于将网格逻辑坐标转换为屏幕像素坐标，实现网格覆盖
- `geopoint`: 经纬度坐标，用于地图定位
- `postSafeguard`: 定义后保护区域（如牵引车作业区），用于目标检测和告警
- `safetyScenarios`: 定义安全场景区域，用于安全监控
- `roi`: 区域多边形坐标，定义具体的安全检测区域边界
