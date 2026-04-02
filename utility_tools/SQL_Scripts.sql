delete from assoc_User_Facility where IDUser >= 8273;
delete from assoc_User_Self where ParentIDUser >= 8273;
delete from assoc_User_Self where ChildIDUser >= 8273;
delete from User where IDUser >= 8273;


select *from LogFileImport where FileName = '2025-09-18_0032e0daf518-045a-4246-b3b7-9ecc033e1503.csv'

DROP PROCEDURE `SaveNewUser`;

DELIMITER $$
CREATE PROCEDURE `SaveNewUser`(xFirstName varchar(60), xLastName varchar(60), xHierarchyLevel1 varchar(40), xHierarchyLevel1Type int, xHierarchyLevel2 varchar(40), xHierarchyLevel2Type int,
xEmail varchar(50), xPassword varchar(250), xRole varchar(150),  xInactive tinyint, xChangePassword tinyint, xSesionToken varchar(150), 
xTokenSesionExpiration datetime, xIDUserType bigint, xLoginAllowed tinyint, xOTP varchar(6), xIDFacility bigint, xIDApprovalStatus bigint, xDeviceID varchar(10), xExternalNumber varchar(50), xPhone varchar(15), xIDHierarchy bigint)
BEGIN 
  
	DECLARE last_id BIGINT;
	
    INSERT INTO User (`FirstName`, `LastName`, `UserId`, `Email`, `Password`, `Role`, `LastUpdateTimestamp`, `SetupTimestamp`, `DeleteTimestamp`, `Inactive`, `TokenApp`,
					`ChangePassword`, `SesionToken`,`TokenSesionExpiration`,`IDUserType`,`HierarchyLevel1`,`HierarchyLevel1Type`,`HierarchyLevel2`,`HierarchyLevel2Type`,`LoginAllowed`,
					`IDApprovalStatus`,`OTP`, `DeviceID`, `ExternalNumber`, `Phone`, `UpdateStatus`, IDHierarchy)
	VALUES (xFirstName, xLastName, xEmail, xEmail, xPassword, xRole, NOW(), NOW(), NULL, 0, NULL, xChangePassword, xSesionToken, xTokenSesionExpiration, xIDUserType,
			xHierarchyLevel1, xHierarchyLevel1Type, xHierarchyLevel2, xHierarchyLevel2Type, xLoginAllowed, xIDApprovalStatus, xOTP, xDeviceID, xExternalNumber, xPhone, 1, xIDHierarchy);

	SET last_id = LAST_INSERT_ID(); 
    
    INSERT INTO assoc_User_Facility (IDUser, IDFacility) VALUES (last_id, xIDFacility);

	select last_id;
    
END$$
DELIMITER ;

call SaveNewUser ('Hadley', 'Jordan', 'Second Grade', 2, 'Mrs. Jamie Bell', 1, 'nan', 'NULL', '{"Admin": false, "readOnly": false, "AppUser": false}', NULL,  NULL, 'NULL', 'NULL', 1, 0, 'NULL', 1, 2, 'NULL', '7440266', 'NULL')

select *from FileVersion

select *from ApprovalStatus

select IDHIerarchy, Description from Hierarchy where IDHierarchyTYpe = 1

select u.IDUser, u.FirstName, u.LastName, u.UserId, u.Email, u.Role, u.ChangePassword, u.TokenSesionExpiration, u.SesionToken, u.Inactive, u.Password, 
                              f.IDFacility, Description, ZoneID, Timezone, IDFacilityGroup, LoginAllowed, u.IDApprovalStatus, u.Phone, u.DeviceID, u.ExternalNumber from Facility f inner join assoc_User_Facility a
                               on a.IDFacility = f.IDFacility inner join User u on u.IDUser=a.IDUser 
                               where (UserId = 'localuser' or Email='localuser') and 
                               DeleteTimestamp is NULL and u.IDUserType != 1

select *from User where LastName = 'Creed'
select *from User where LastName = 'Roberts'

select *from assoc_User_Hierarchy

select *from User where IDUser > 13193

select *from Hierarch

insert into assoc_User_Facility (IDUser, IDFacility) values (13195, 1)

select *from FileVersion
inser

INSERT INTO `mvp_school`.`User`
(`FirstName`,`LastName`,`UserId`,`Email`,`Password`,
`Role`,
`LastUpdateTimestamp`,
`SetupTimestamp`,
`DeleteTimestamp`,
`Inactive`,
`TokenApp`,
`ChangePassword`,
`SesionToken`,
`TokenSesionExpiration`,
`IDUserType`,
`HierarchyLevel1`,
`HierarchyLevel1Type`,
`HierarchyLevel2`,
`HierarchyLevel2Type`,
`LoginAllowed`,
`IDApprovalStatus`,
`OTP`,
`IDPAUser`,
`ExternalNumber`,
`Phone`,
`DeviceID`,
`UpdateStatus`,
`IDHierarchy`)
VALUES
('Amanda', 'Stephens',
    'stephensa@svdpschool.net',
    'stephensa@svdpschool.net',
    '3c9dc5f18445cfc46c86b971e43a459b0ec3511dab30ca20be142e56abc56d9ac743dc62860623de965193e53a61cedbec591ac795a1ab9875b9707601957c49a5760d70e591b809bf690bf015ff7fc6f453c7f3571900553a6acfab6f1eac44',
    '{\"Admin\": false, \"readOnly\": false, \"SuperUser\": false, \"DownloadData\": false, \"StudentGrid\": true}',
    NOW(), 
    NOW(), 
    NULL, 
    '0', 
    NULL, 
    '0', 
    NULL, 
    NULL, 
    '3', 
    '12', 
    '2', 
    '89', 
    '1', 
    '0', 
    '2', 
    '0', NULL, NULL, NULL, NULL, '1', NULL);

12:20:54	INSERT INTO `mvp_school`.`User` (`FirstName`,`LastName`,`UserId`,`Email`,`Password`, `Role`, `LastUpdateTimestamp`, `SetupTimestamp`, `DeleteTimestamp`, `Inactive`, `TokenApp`, `ChangePassword`, `SesionToken`, `TokenSesionExpiration`, `IDUserType`, `HierarchyLevel1`, `HierarchyLevel1Type`, `HierarchyLevel2`, `HierarchyLevel2Type`, `LoginAllowed`, `IDApprovalStatus`, `OTP`, `IDPAUser`, `ExternalNumber`, `Phone`, `DeviceID`, `UpdateStatus`, `IDHierarchy`) VALUES ('Amanda', 'Stephens',     'stephensa@svdpschool.net',     'stephensa@svdpschool.net',     '3c9dc5f18445cfc46c86b971e43a459b0ec3511dab30ca20be142e56abc56d9ac743dc62860623de965193e53a61cedbec591ac795a1ab9875b9707601957c49a5760d70e591b809bf690bf015ff7fc6f453c7f3571900553a6acfab6f1eac44',     '{\"Admin\": false, \"readOnly\": false, \"SuperUser\": false, \"DownloadData\": false, \"StudentGrid\": true}',     NOW(),      NOW(),      NULL,      '0',      NULL,      '0',      NULL,      NULL,      '3',      '12',      '2',      '89',      '1',      '0',      '2',      '0', NULL, NULL, NULL, NULL, '1', NULL) FROM `mvp_school`.`User`	Error Code: 1064. You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near 'FROM `mvp_school`.`User`' at line 48	0.077 sec


where LastName = 'Web'

select IDHierarchy, FirstName, LastName, ExternalNumber, DeviceID from User where HierarchyLevel1 = 'Fifth Grade' 
and HierarchyLevel2 = 'Miss Grace Webb'


IDHierarchy in (77, 84)

77 Stephens
84 Webb 

select *from Hierarchy

ExternalNumber = '33710871'

select *from HystoricPassword 

select u.IDUser, u.FirstName, u.LastName, u.UserId, u.Email, u.Role, u.ChangePassword, u.TokenSesionExpiration, 
u.SesionToken, u.Inactive, u.Password, f.IDFacility, Description, ZoneID, Timezone, IDFacilityGroup, 
LoginAllowed, u.IDApprovalStatus, u.Phone, u.DeviceID, u.ExternalNumber from Facility f
 inner join assoc_User_Facility a on a.IDFacility = f.IDFacility inner join User u on u.IDUser=a.IDUser 
 where (UserId = 'admin@iqright.app' or Email='admin@iqright.app') and 
 DeleteTimestamp is NULL and u.IDUserType != 1 and LoginAllowed = True

select *from UserType
select *from assoc_User_Self where ParentIDUser=11929

select u.IDUser, u.FirstName, u.LastName, u.UserId, u.Email, u.Role, u.ChangePassword, u.TokenSesionExpiration, u.SesionToken, u.Inactive, u.Password, 
f.IDFacility, Description, ZoneID, Timezone, IDFacilityGroup, LoginAllowed, u.IDApprovalStatus, u.Phone, u.DeviceID, u.ExternalNumber 
from Facility f 
inner join assoc_User_Facility a on a.IDFacility = f.IDFacility 
inner join User u on u.IDUser=a.IDUser where 
(UserId = 'fulviomanente@gmail.com' or Email='fulviomanente@gmail.com') and DeleteTimestamp is NULL and u.IDUserType != 1

select IDUser, ExternalNumber, FirstName, LastName, HierarchyLevel1, HierarchyLevel2, IDUserType from User where LastName = 'Harris'

select IDUser, Length(ExternalNumber) from User 
where Length(ExternalNumber) > 9

##update User set DeviceID=concat("P",ExternalNumber) where IDUserType=2 and IDUser in(
##select ParentIDUser from assoc_User_Self)

Select u2.IDUser as ChildID, u.IDUser,  u.FirstName, u.LastName, u.IDApprovalStatus as AppIDApprovalStatus, 
ast.Description as AppApprovalStatus,u.DeviceID, u.Phone, concat(u2.FirstName, ' ',u2.LastName) as ChildName, u2.ExternalNumber, 
u2.HierarchyLevel1, u2.HierarchyLevel1Type, h1.Description as HierarchyLevel1Desc, u2.HierarchyLevel2, u2.HierarchyLevel2Type,
h2.Description as HierarchyLevel2Desc, au.StartDate, au.ExpireDate, au.IDApprovalStatus, ast2.Description as ApprovalStatus, 
au.MainContact, au.Relationship, u2.IDHierarchy 
from User u 
inner join assoc_User_Self au USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on au.ParentIDUser=u.IDUser 
inner join User u2 on u2.IDUser = au.ChildIDUser 
inner join ApprovalStatus ast on ast.IDApprovalStatus=u.IDApprovalStatus and ast.IDFacility = 1 
inner join ApprovalStatus ast2 on ast2.IDApprovalStatus=au.IDApprovalStatus 
and ast.IDFacility = 1 inner join HierarchyType h1 on h1.IDHierarchyType=u2.HierarchyLevel1Type inner join HierarchyType h2 on 
h2.IDHierarchyType=u2.HierarchyLevel2Type where u.DeleteTimestamp is NULL and u.IDUserType = 2
and u.DeviceID='5510282'

select *from User where 

Update User set DeviceID='P6410266' where DeviceID = '6410266' 

##AJUSTAR
#u.DeviceID='1316500777'

#Update User set DeviceID = '6410266' where DeviceID='P6410266'

#select *from User where IDUser in(
#select ParentIDUser from 
#User u inner join assoc_User_Self aus on aus.ChildIDUser=u.IDUser where ExternalNumber = '35110078')

delete from assoc_User_Self
where ParentIDUser=ChildIDUser

select *from assoc_User_Self where ChildIDUser in (
select ParentIDUser from assoc_User_Self
where ParentIDUser=ChildIDUser)

select *from User where IDUser in(
select ParentIDUser from assoc_User_Self aus 
where ParentIDUser in (Select IDUser from User where IDUserType = 1))

select *from User where ExternalNumber = '2910172'

select '5510282' into @ExternalNumber;

#Insert Generic User
insert into User (FirstName, LastName, userId, Email, Role, LastUpdateTimestamp, SetupTimestamp, Inactive, IDUserType, LoginAllowed, IDApprovalStatus, OTP, ExternalNumber, Phone, DeviceID, UpdateStatus)
select 'Generic', 'QRCode', UserId, Email, Role, NOW(), NOW(), 0, 2, 0, 5, 'Invalid', NULL, Phone, @ExternalNumber, 1 from User where IDUser in(
select min(IDUser) from User where IDUser in(
select ParentIDUser from 
User u inner join assoc_User_Self aus on aus.ChildIDUser=u.IDUser where ExternalNumber = @ExternalNumber and MainContact=True)
);

select LAST_INSERT_ID() into @newUser;

#Generate association with same users
insert into assoc_User_Self(ParentIDUser, ChildIDUser, Timestamp, Relationship, StartDate, IDApprovalStatus, MainContact)
select LAST_INSERT_ID(), ChildIDUser, NOW(), 'Temporary', DATE(NOW()), 2, 1 from assoc_User_Self where ParentIDUser in(
select min(IDUser) from User where IDUser in(
select ParentIDUser from 
User u inner join assoc_User_Self aus on aus.ChildIDUser=u.IDUser where ExternalNumber = @ExternalNumber and MainContact=True)
);


insert into assoc_User_Facility (IDUser, IDFacility) select @newUser, 1;


delete from User where IDUser = 13166

select max(IDUser) from User where IDUser in (10921, 10922)

select
select *from assoc_User_Self where ParentIDUser in (13167)


##NEW SQL
select parent.IDUser as parent, kid.IDUser as child, parent.ExternalNumber, parent.FirstName, parent.LastName, kid.FirstName as ChildName, kid.LastName as ChildLastName, kid.HierarchyLevel1, kid.HierarchyLevel2, kid.IDUserType 
from User parent inner join assoc_User_Self aus on aus.ParentIDuser=parent.IDUser
inner join User kid on kid.IDUser=aus.ChildIDUser and aus.MainContact = True
where parent.ExternalNumber = '8330266'

select parent.IDUser as parent, kid.IDUser as child, parent.ExternalNumber, parent.FirstName, parent.LastName, kid.FirstName as ChildName, kid.LastName as ChildLastName, kid.HierarchyLevel1, kid.HierarchyLevel2, kid.IDUserType 
from User parent inner join assoc_User_Self aus on aus.ParentIDuser=parent.IDUser
inner join User kid on kid.IDUser=aus.ChildIDUser
where parent.IDUser = 10919


select count(0),ParentIDUser from assoc_User_Self
group by ParentIDUser
having count(0) > 2

select *from assoc_User_Self where ChildIDUser = 11813

select * from User where IDUserType=2 and 
IDUser > 10000 and 
IDUser not in (select ParentIDUser from assoc_User_Self)

select *from User where IDUser in (13163, 13164, 13165)


select p.FirstName, p.LastName, k.FirstName, k.LastName, p.ExternalNumber, k.HierarchyLevel1 from 
User p inner join assoc_User_Self a on a.ParentIDUser=p.IDUser
inner join User k on k.IDUser=a.ChildIDUser


select p.FirstName, p. LastName, p.ExternalNumber, k.FirstName, k.LastName, k.HierarchyLevel1 from User p inner join assoc_User_Self a on a.ParentIDUser=p.IDUser inner join User k on k.IDUser=a.ChildIDUser 
where MainContact = 1
order by p.ExternalNumber, k.FirstName, k.LastName

select *from FileVersion where IDFileVersion > 15

##LOGIN QUERY
select u.IDUser, u.FirstName, u.LastName, u.UserId, u.Email, u.Role, u.ChangePassword, 
u.TokenSesionExpiration, u.SesionToken, u.Inactive, u.Password, f.IDFacility, 
Description, ZoneID, Timezone, IDFacilityGroup, LoginAllowed, u.IDApprovalStatus, 
u.Phone, u.DeviceID, u.ExternalNumber from Facility f inner join assoc_User_Facility a on 
a.IDFacility = f.IDFacility inner join User u on u.IDUser=a.IDUser where (UserId = 'webbg@svdpschool.net' or 
Email='webbg@svdpschool.net') and DeleteTimestamp is NULL and LoginAllowed = True

select *from HystoricPassword where IDUser = 11928

select *from User where ExternalNumber = 14510480

select *from assoc_User_Hierarchy where IDUser = 13193

 Email = 'stephensa@svdpschool.net'

select *from Hierarchy

select *from LoginHistory where IDUser in (1, 11928)

Select * From LoginHistory where IDUser=13194 order by IDLoginHistory Desc limit 3

select *from User where LastName like '%Michael%'

select *from assoc_User_Self

INSERT INTO `mvp_school`.`assoc_User_Facility` (`IDUser`, `IDFacility`) VALUES ('13198', '1');
INSERT INTO `mvp_school`.`assoc_User_Facility` (`IDUser`, `IDFacility`) VALUES ('13200', '1');

13189
update User set Password = '3c9dc5f18445cfc46c86b971e43a459b0ec3511dab30ca20be142e56abc56d9ac743dc62860623de965193e53a61cedbec591ac795a1ab9875b9707601957c49a5760d70e591b809bf690bf015ff7fc6f453c7f3571900553a6acfab6f1eac44'
where IDUser = 1


update User set Password = '3c9dc5f18445cfc46c86b971e43a459b0ec3511dab30ca20be142e56abc56d9ac743dc62860623de965193e53a61cedbec591ac795a1ab9875b9707601957c49a5760d70e591b809bf690bf015ff7fc6f453c7f3571900553a6acfab6f1eac44'
where IDUser = 13195

webbg '73cbd8978b0f69bf3a956d13fdd1ff0a7f1793ba41bad84adb443e4732220b3728ff864c25b27db49ad1f497e3d9ed7e6b8c0611c770a7bf4b9ad091af4674481ce48ea0ef37fdca8125394930aa4dc5d9b64f70dc72ed111eeddc576260aa8f'
stephensa 

update User set Password = '73cbd8978b0f69bf3a956d13fdd1ff0a7f1793ba41bad84adb443e4732220b3728ff864c25b27db49ad1f497e3d9ed7e6b8c0611c770a7bf4b9ad091af4674481ce48ea0ef37fdca8125394930aa4dc5d9b64f70dc72ed111eeddc576260aa8f'
where IDUser = 13194


select *from assoc_User_Facility where IDUser = 1 

insert into assoc_User_Facility (IDUser, IDFacility) values (1, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (297, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (298, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (299, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (336, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (337, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (338, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (339, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (340, 1);


Select u2.IDUser as ChildID, u.IDUser,  u.FirstName, u.LastName, u.IDApprovalStatus as AppIDApprovalStatus, 
ast.Description as AppApprovalStatus,u.DeviceID, u.Phone, concat(u2.FirstName, ' ',u2.LastName) as ChildName, u2.ExternalNumber, 
u2.HierarchyLevel1, u2.HierarchyLevel1Type, h1.Description as HierarchyLevel1Desc, u2.HierarchyLevel2, u2.HierarchyLevel2Type, 
h2.Description as HierarchyLevel2Desc, au.StartDate, au.ExpireDate, au.IDApprovalStatus, ast2.Description as ApprovalStatus, 
au.MainContact, au.Relationship, u2.IDHierarchy from User u inner join assoc_User_Self au USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on 
au.ParentIDUser=u.IDUser inner join User u2 on u2.IDUser = au.ChildIDUser inner join ApprovalStatus ast on 
ast.IDApprovalStatus=u.IDApprovalStatus and ast.IDFacility = 1 inner join ApprovalStatus ast2 on ast2.IDApprovalStatus=au.IDApprovalStatus 
and ast.IDFacility = 1 inner join HierarchyType h1 on h1.IDHierarchyType=u2.HierarchyLevel1Type inner join HierarchyType h2 on 
h2.IDHierarchyType=u2.HierarchyLevel2Type where u.DeleteTimestamp is NULL and u.IDUserType = 2 and u2.ExternalNumber = '6610282'


select *from User where LastName like '%Serrano%'


Select u.IDUser, u.FirstName, u.LastName, u.HierarchyLevel1, u.HierarchyLevel2, u.ExternalNumber, 
p.FirstName as pFirstName, p.LastName as pLastName, p.Email, p.Phone, ap.IDApprovalStatus, 
ap.Description as ApprovalStatus, aus.ExpireDate, aus.Relationship, p.IDUser as pIDUser , 
aus.MainContact from User u left join assoc_User_Facility auf on auf.IDUser=u.IDUser and auf.IDFacility=1 
left join assoc_User_Self aus on aus.ChildIDUser=u.IDUser and aus.IDApprovalStatus in (2,4,6,1,5) 
left join User p on p.IDUser=aus.ParentIDUser and p.DeleteTimestamp is NULL and p.Inactive=0 and
 p.IDApprovalStatus in (2,4,6,1,5) left join ApprovalStatus ap on ap.IDApprovalStatus=p.IDApprovalStatus 
 where u.DeleteTimestamp is NULL and u.IDUserType = 1 
 and u.LastName like '%Torrez%' 
 
 select *from User where DeviceID = 'P4710282'

SELECT *from (
SELECT p.ExternalNumber, k.FirstName, k.LastName, 
        k.HierarchyLevel1, CASE
             WHEN EXISTS (
                 SELECT 1 FROM User k2
                 INNER JOIN assoc_User_Self a2 ON a2.ChildIDUser = k2.IDUser
                 WHERE a2.ParentIDUser = p.IDUser
                 AND a2.MainContact = 1
                 AND k2.HierarchyLevel1 IN ('First Grade', 'Second Grade')
             ) THEN 1
             ELSE 2
         END AS ParentGroup FROM User p
        INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
        INNER JOIN User k ON k.IDUser = a.ChildIDUser
        WHERE MainContact = 1
        and k.LastName = 'Ayala'
        AND p.IDUser = (
            SELECT MIN(p2.IDUser) FROM User p2 INNER JOIN assoc_User_Self a2 ON a2.ParentIDUser = p2.IDUser
            WHERE a2.ChildIDUser = k.IDUser AND a2.MainContact = 1)) t 
		where t.ParentGroup = 1
        ORDER BY ExternalNumber, FirstName, LastName

SELECT *from (
SELECT p.ExternalNumber, k.FirstName, k.LastName, 
        k.HierarchyLevel1, CASE
             WHEN EXISTS (
                 SELECT 1 FROM User k2
                 INNER JOIN assoc_User_Self a2 ON a2.ChildIDUser = k2.IDUser
                 WHERE a2.ParentIDUser = p.IDUser
                 AND a2.MainContact = 1
                 AND k2.HierarchyLevel1 IN ('Kindergarten')
             ) THEN 1
             ELSE 2
         END AS ParentGroup FROM User p
        INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
        INNER JOIN User k ON k.IDUser = a.ChildIDUser
        WHERE MainContact = 1
        AND p.IDUser = (
            SELECT MIN(p2.IDUser) FROM User p2 INNER JOIN assoc_User_Self a2 ON a2.ParentIDUser = p2.IDUser
            WHERE a2.ChildIDUser = k.IDUser AND a2.MainContact = 1)) t 
		where t.ParentGroup = 1
        ORDER BY ExternalNumber, FirstName, LastName

SELECT *from (
SELECT p.DeviceID, k.DeviceID as parentQR, k.FirstName, k.LastName, 
        k.HierarchyLevel1, CASE
             WHEN EXISTS (
                 SELECT 1 FROM User k2
                 INNER JOIN assoc_User_Self a2 ON a2.ChildIDUser = k2.IDUser
                 WHERE a2.ParentIDUser = p.IDUser
                 AND a2.MainContact = 1
                 AND k2.HierarchyLevel1 IN ('Fifth Grade')
             ) THEN 1
             ELSE 2
         END AS ParentGroup FROM User p
        INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
        INNER JOIN User k ON k.IDUser = a.ChildIDUser
        WHERE MainContact = 1
        AND p.IDUser = (
            SELECT MIN(p2.IDUser) FROM User p2 INNER JOIN assoc_User_Self a2 ON a2.ParentIDUser = p2.IDUser
            WHERE a2.ChildIDUser = k.IDUser AND a2.MainContact = 1)) t 
		where t.ParentGroup = 1
        ORDER BY DeviceID, FirstName, LastName
        
        SELECT *from (
SELECT p.DeviceID, k.DeviceID as parentQR, k.FirstName, k.LastName, 
        k.HierarchyLevel1
		FROM User p
        INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
        INNER JOIN User k ON k.IDUser = a.ChildIDUser
        WHERE MainContact = 1
        AND k.HierarchyLevel1 IN ('Fifth Grade') and k.HierarchyLevel2 in ('Miss Grace Webb')
        AND p.IDUser = (
            SELECT MIN(p2.IDUser) FROM User p2 INNER JOIN assoc_User_Self a2 ON a2.ParentIDUser = p2.IDUser
            WHERE a2.ChildIDUser = k.IDUser AND a2.MainContact = 1 and p2.DeviceID is not null)
        ORDER BY DeviceID, FirstName, LastName
        
        SELECT p.DeviceID, k.DeviceID as parentQR, k.FirstName, k.LastName, 
                            k.HierarchyLevel1
                            FROM User p
                            INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
                            INNER JOIN User k ON k.IDUser = a.ChildIDUser
                            WHERE MainContact = 1
                            AND k.HierarchyLevel1 IN ('Fifth Grade')
                            AND p.IDUser = (
                                SELECT MIN(p2.IDUser) FROM User p2 INNER JOIN assoc_User_Self a2 ON a2.ParentIDUser = p2.IDUser
                                WHERE a2.ChildIDUser = k.IDUser AND a2.MainContact = 1 and p2.DeviceID is not null)
                            ORDER BY DeviceID, FirstName, LastName

select p.* from User p 
INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
where LEFT(DeviceID, 1) <> 'P'


select DeviceID, count(0) from User 
group by DeviceID having count(0) > 1 

select p.* from User p 
where DeviceID = 'P25720672'
lastName = 'OCarroll' or lastName = 'OCarrol' 


################NEED A NEW QR CODE
update User set DeviceID = 'P21640583' where IDUser = 12101
update User set DeviceID = 'P131630583' where IDUser = 13164

131630583

select p.DeviceID, k.* from User p 
INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
INNER JOIN User k ON k.IDUser = a.ChildIDUser
where p.IDUser in (12101, 13164)

select p.DeviceID, k.* from User p 
INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
INNER JOIN User k ON k.IDUser = a.ChildIDUser
where k.IDUser in (12333, 13163, 13165, 12824)

select IDHierarchy, Description, ExternalCode as ClassCode from Hierarchy where IDHierarchyType = 1

Select u2.IDUser as ChildID, u.IDUser,  u.FirstName, u.LastName, u.IDApprovalStatus as AppIDApprovalStatus, 
                     ast.Description as AppApprovalStatus,u.DeviceID, u.Phone, concat(u2.FirstName, ' ',u2.LastName) as ChildName, u2.ExternalNumber, 
                     u2.HierarchyLevel1, u2.HierarchyLevel1Type, h1.Description as HierarchyLevel1Desc, u2.HierarchyLevel2, u2.HierarchyLevel2Type, 
                     h2.Description as HierarchyLevel2Desc, au.StartDate, au.ExpireDate, au.IDApprovalStatus, ast2.Description as ApprovalStatus, 
                     au.MainContact, au.Relationship, u2.IDHierarchy, ExternalCode as ClassCode from User u inner join assoc_User_Self au USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on 
                     au.ParentIDUser=u.IDUser inner join User u2 on u2.IDUser = au.ChildIDUser inner join ApprovalStatus ast on 
                     ast.IDApprovalStatus=u.IDApprovalStatus and ast.IDFacility = 1 inner join ApprovalStatus ast2 on ast2.IDApprovalStatus=au.IDApprovalStatus 
                     and ast.IDFacility = 1 inner join HierarchyType h1 on h1.IDHierarchyType=u2.HierarchyLevel1Type inner join HierarchyType h2 on 
                     h2.IDHierarchyType=u2.HierarchyLevel2Type inner join Hierarchy h on h.IDHIerarchy=u2.IDHierarchy where u.DeleteTimestamp is NULL and u.IDUserType = 2


select u.IDUser, u.FirstName, u.LastName, u.UserId, u.Email, u.Role, u.ChangePassword, u.TokenSesionExpiration, u.SesionToken, 
u.Inactive, u.Password, f.IDFacility, Description, ZoneID, Timezone, IDFacilityGroup, LoginAllowed, u.IDApprovalStatus, u.Phone, 
u.DeviceID, u.ExternalNumber from Facility f inner join assoc_User_Facility a on a.IDFacility = f.IDFacility inner join User u on u.IDUser=a.IDUser 
where (UserId = 'caseyr@svdpschool.net' or Email='caseyr@svdpschool.net') and DeleteTimestamp is NULL and u.IDUserType != 1

select *from User where Email = 'caseyr@svdpschool.net'

select *from UserType




Select au.id, u2.IDUser as ChildID, u.IDUser,  u.FirstName, u.LastName, concat(u2.FirstName, ' ',u2.LastName) as ChildName, au.Relationship,
u.IDApprovalStatus as AppIDApprovalStatus, 
ast.Description as AppApprovalStatus,u.DeviceID, u.Phone,  u2.ExternalNumber, 
u2.HierarchyLevel1, u2.HierarchyLevel1Type, h1.Description as HierarchyLevel1Desc, u2.HierarchyLevel2, u2.HierarchyLevel2Type, 
h2.Description as HierarchyLevel2Desc, au.StartDate, au.ExpireDate, au.IDApprovalStatus, ast2.Description as ApprovalStatus, 
au.MainContact, au.Relationship, u2.IDHierarchy from 
User u 
inner join assoc_User_Self au USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on au.ParentIDUser=u.IDUser 
inner join User u2 on u2.IDUser = au.ChildIDUser 
inner join ApprovalStatus ast on ast.IDApprovalStatus=u.IDApprovalStatus and ast.IDFacility = 1 
inner join ApprovalStatus ast2 on ast2.IDApprovalStatus=au.IDApprovalStatus and ast.IDFacility = 1 
inner join HierarchyType h1 on h1.IDHierarchyType=u2.HierarchyLevel1Type 
inner join HierarchyType h2 on h2.IDHierarchyType=u2.HierarchyLevel2Type 
where u.DeleteTimestamp is NULL and u.IDUserType = 2 and au.Relationship not in ('Mother', 'Father', 'Grandparent', 'Step Father',
'Step Mother', 'Brother', 'Sister')
order by u.LastName, u.FirstName

Select u2.IDUser as ChildID, u.IDUser,  u.FirstName, u.LastName, u.IDApprovalStatus as AppIDApprovalStatus, 
ast.Description as AppApprovalStatus,u.DeviceID, u.Phone, concat(u2.FirstName, ' ',u2.LastName) as ChildName, u2.ExternalNumber, 
u2.HierarchyLevel1, u2.HierarchyLevel1Type, h1.Description as HierarchyLevel1Desc, u2.HierarchyLevel2, u2.HierarchyLevel2Type, 
h2.Description as HierarchyLevel2Desc, au.StartDate, au.ExpireDate, au.IDApprovalStatus, ast2.Description as ApprovalStatus, 
au.MainContact, au.Relationship, u2.IDHierarchy from User u inner join assoc_User_Self au USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on 
au.ParentIDUser=u.IDUser inner join User u2 on u2.IDUser = au.ChildIDUser inner join ApprovalStatus ast on 
ast.IDApprovalStatus=u.IDApprovalStatus and ast.IDFacility = 1 inner join ApprovalStatus ast2 on ast2.IDApprovalStatus=au.IDApprovalStatus 
and ast.IDFacility = 1 inner join HierarchyType h1 on h1.IDHierarchyType=u2.HierarchyLevel1Type inner join HierarchyType h2 on 
h2.IDHierarchyType=u2.HierarchyLevel2Type where u.DeleteTimestamp is NULL and u.IDUserType = 2 and ChildID in (12078, 12079, 11307, 12872, 12939, 12035, 12277, 11432, 11424
12527, 12338, )




Select au.id, u2.IDUser as ChildID, u.IDUser,  u.FirstName, u.LastName, concat(u2.FirstName, ' ',u2.LastName) as ChildName, au.Relationship,
u.IDApprovalStatus as AppIDApprovalStatus, 
ast.Description as AppApprovalStatus,u.DeviceID, u.Phone,  u2.ExternalNumber, 
u2.HierarchyLevel1, u2.HierarchyLevel1Type, h1.Description as HierarchyLevel1Desc, u2.HierarchyLevel2, u2.HierarchyLevel2Type, 
h2.Description as HierarchyLevel2Desc, au.StartDate, au.ExpireDate, au.IDApprovalStatus, ast2.Description as ApprovalStatus, 
au.MainContact, au.Relationship, u2.IDHierarchy from 
User u 
inner join assoc_User_Self au USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on au.ParentIDUser=u.IDUser 
inner join User u2 on u2.IDUser = au.ChildIDUser 
inner join ApprovalStatus ast on ast.IDApprovalStatus=u.IDApprovalStatus and ast.IDFacility = 1 
inner join ApprovalStatus ast2 on ast2.IDApprovalStatus=au.IDApprovalStatus and ast.IDFacility = 1 
inner join HierarchyType h1 on h1.IDHierarchyType=u2.HierarchyLevel1Type 
inner join HierarchyType h2 on h2.IDHierarchyType=u2.HierarchyLevel2Type 
where u.DeleteTimestamp is NULL and u.IDUserType = 2 and u.IDUser in(
Select u10.IDUser from 
User u10 
inner join assoc_User_Self au10 USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on au10.ParentIDUser=u10.IDUser 
inner join User u210 on u210.IDUser = au10.ChildIDUser 
inner join ApprovalStatus ast10 on ast10.IDApprovalStatus=u10.IDApprovalStatus and ast10.IDFacility = 1 
inner join ApprovalStatus ast210 on ast210.IDApprovalStatus=au10.IDApprovalStatus and ast210.IDFacility = 1 
where u10.DeleteTimestamp is NULL and u10.IDUserType = 2 and au10.Relationship not in ('Mother', 'Father', 'Grandparent', 'Step Father',
'Step Mother', 'Brother', 'Sister'))
order by u.LastName, u.FirstName

delete from assoc_User_Self where id in (
8257, 8687, 8831, 8508, 9182, 8158, 8191, 8628, 8717, 8945, 9072, 146, 8151, 8592, 8889, 9058, 8001, 8028, 8485, 8489, 8863, 8882, 9048, 7725, 8667, 8414,9001, 9326,
8029, 8186, 8444, 8864, 9196, 9255, 7724, 8666, 8185, 8443, 9254, 9447, 8997, 9288, 9580, 8996, 9287, 9335, 9579, 8548, 8678, 9159, 9721, 9722, 9334, 8157,
8413, 8716, 9002, 9325, 8002, 8020, 8484, 8490, 8535, 8881, 8938, 9049, 8998, 9290, 9583, 9448, 8677, 9263)

12286John Harrintgton
s

select *from User where LastName like '%Gollhofer%'

select *from Hierarchy

select *from User where UserId like '%localuser%'

select *from HystoricPassword where IDUser = 337

INSERT INTO `mvp_school`.`User` (`FirstName`, `LastName`, `UserId`, `Email`, `Password`, `Role`, `LastUpdateTimestamp`, `SetupTimestamp`, `Inactive`, `ChangePassword`, `IDUserType`, `HierarchyLevel1`, `HierarchyLevel1Type`, `HierarchyLevel2`, `HierarchyLevel2Type`, `LoginAllowed`, `IDApprovalStatus`, `OTP`, `UpdateStatus`) 
VALUES 
('Luffman', 'Ginny', 'luffmang@svdpschool.net', 'luffmang@svdpschool.net', 'c3e3b22bae61a4d25bf154781326d7a81b1849c41a888fe1899126d915ccfcfffe66a4688fecfd3fdc9b7f9164fd051d37b380a706f836cfb6ba9a050d1f51f0ec766f7c370bfa90ba4312bfc7a29c7964811c4eb2fddbbab8b0697b37e7b796', 
'{\"Admin\": false, \"readOnly\": false, \"SuperUser\": false, \"DownloadData\": false, \"StudentGrid\": true}', '2025-12-16 18:21:30', '2025-12-16 18:21:30', '0', '0', '3', '4', '2', '98', '1', '0', '2', '0', '1');

insert into assoc_User_Facility (IDUser, IDFacility) values (13205, 1);
insert into assoc_User_Facility (IDUser, IDFacility) values (13206, 1);

select *from User where IDUser in (13203, 13204)


select *from Hierarchy

select *from LoginHistory where IDUser = 13202
select *from assoc_User_Hierarchy

Select u2.IDUser as ChildID, u.IDUser,  u.FirstName, u.LastName, u.IDApprovalStatus as AppIDApprovalStatus, 
                     ast.Description as AppApprovalStatus,u.DeviceID, u.Phone, concat(u2.FirstName, ' ',u2.LastName) as ChildName, u2.ExternalNumber, 
                     u2.HierarchyLevel1, u2.HierarchyLevel1Type, h1.Description as HierarchyLevel1Desc, u2.HierarchyLevel2, u2.HierarchyLevel2Type, 
                     h2.Description as HierarchyLevel2Desc, au.StartDate, au.ExpireDate, au.IDApprovalStatus, ast2.Description as ApprovalStatus, 
                     au.MainContact, au.Relationship, u2.IDHierarchy, ExternalCode as ClassCode from User u inner join assoc_User_Self au USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on 
                     au.ParentIDUser=u.IDUser inner join User u2 on u2.IDUser = au.ChildIDUser inner join ApprovalStatus ast on 
                     ast.IDApprovalStatus=u.IDApprovalStatus and ast.IDFacility = 1 inner join ApprovalStatus ast2 on ast2.IDApprovalStatus=au.IDApprovalStatus 
                     and ast.IDFacility = 1 inner join HierarchyType h1 on h1.IDHierarchyType=u2.HierarchyLevel1Type inner join HierarchyType h2 on 
                     h2.IDHierarchyType=u2.HierarchyLevel2Type inner join Hierarchy h on h.IDHIerarchy=u2.IDHierarchy where u.DeleteTimestamp is NULL and u.IDUserType = 2
                     and u2.lastName = 'Ottrix'
                     
                     select *from User where DeviceID = 'P17020467'
                     
                     SELECT p.DeviceID, k.DeviceID as parentQR, k.FirstName, k.LastName, 
                            k.HierarchyLevel1
                            FROM User p
                            INNER JOIN assoc_User_Self a ON a.ParentIDUser = p.IDUser
                            INNER JOIN User k ON k.IDUser = a.ChildIDUser
                            WHERE MainContact = 1
                            AND k.HierarchyLevel1 IN ('Sixth Grade')
                            AND p.IDUser = (
                                SELECT MIN(p2.IDUser) FROM User p2 INNER JOIN assoc_User_Self a2 ON a2.ParentIDUser = p2.IDUser
                                WHERE a2.ChildIDUser = k.IDUser AND a2.MainContact = 1 and p2.DeviceID is not null)
                            ORDER BY DeviceID, FirstName, LastName
                            
                            
                            select a.ID, a.ChildIDUser, u.*from assoc_User_Self a inner join User u on a.ParentIDUser=u.IDUser where a.ChildIDUser in (
                            select IDUser from User where LastName in ('Johnston', 'Gallegos')) order by FirstName, LastName
                            
                            select *from User where LastName = 'Ottrix'
                            
                            select *from assoc_User_Facility where IDUser in (13203, 13204) 
                            
                            select *from Hierarchy
                            
                            delete from assoc_User_Self where id in (8665, 7723)
                            
                           select *from User where IDUser in (13164) 
 

#FileVersion
 
select *from FileVersion
 
#File Download Query 03-02-2026
                            
Select u2.IDUser as ChildID, u.IDUser,  u.FirstName, u.LastName, u.IDApprovalStatus as AppIDApprovalStatus, ast.Description as AppApprovalStatus,
u.DeviceID, u.Phone, concat(u2.FirstName, ' ',u2.LastName) as ChildName, u2.ExternalNumber, u2.HierarchyLevel1, u2.HierarchyLevel1Type, h1.Description as HierarchyLevel1Desc,
u2.HierarchyLevel2, u2.HierarchyLevel2Type, h2.Description as HierarchyLevel2Desc, au.StartDate, au.ExpireDate, au.IDApprovalStatus, ast2.Description as ApprovalStatus, 
au.MainContact, au.Relationship, u2.IDHierarchy, ExternalCode as ClassCode 
#select distinct u2.FirstName, u2.LastName, concat('P', u2.ExternalNumber) as DeviceID, h.ExternalCode as Grade
from User u 
inner join assoc_User_Self au USE INDEX (idx_assoc_User_Self_ParentChild_IDs) on au.ParentIDUser=u.IDUser 
inner join User u2 on u2.IDUser = au.ChildIDUser 
inner join ApprovalStatus ast on ast.IDApprovalStatus=u.IDApprovalStatus and ast.IDFacility = 1 
inner join ApprovalStatus ast2 on ast2.IDApprovalStatus=au.IDApprovalStatus and ast.IDFacility = 1 
inner join HierarchyType h1 on h1.IDHierarchyType=u2.HierarchyLevel1Type 
inner join HierarchyType h2 on h2.IDHierarchyType=u2.HierarchyLevel2Type 
inner join Hierarchy h on h.IDHIerarchy=u2.IDHierarchy 
where u.DeleteTimestamp is NULL and u.IDUserType = 2
#and u2.IDUser in (13163, 13165)
and u2.LastName = 'Clark'
#and u2.ExternalNumber like '%25010672%'
#and u.DeviceID = 'P25010672'

select *from User where ExternalNumber = '13163058'

select *from Hierarchy

IDUser = 11739
33410871

select *from User where IDUser = 11309
24610672

delete from assoc_User_Self where ParentIDUser = 13173 and ChildIDUser in (11277, 11457, 11759, 12257, 12647, 12712) 


select *from User where LastName = 'Golhofer'