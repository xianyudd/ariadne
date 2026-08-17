# Valid dependency graph

- [x] T001 [US1] Foundation
  Depends:
  Story: US1
  Area: model
  Risk: normal
- [ ] T002 [US1] Implementation
  Depends: T001
  Story: US1
  Area: app
  Risk: normal
- [ ] T003 [US1] Verification
  Depends: T002
  Story: US1
  Area: tests
  Risk: normal
